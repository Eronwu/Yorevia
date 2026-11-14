#!/usr/bin/env python3
"""Publish this checkout with the user's own authenticated GitHub CLI.
Never reads tokens directly, force-pushes, changes global Git settings, or uploads a vault.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PUBLIC_PATHS=[
    '.github','.gitignore','LICENSE','NOTICE','README.md','README.en.md',
    'SECURITY.md','CONTRIBUTING.md','THIRD_PARTY_NOTICES.md','package.json',
    'package-lock.json','tsconfig.json','pyproject.toml','requirements.txt',
    'requirements-dev.txt','src','public','engine','tests','scripts','docs',
    'models/manifest.json','src-tauri/Cargo.toml','src-tauri/Cargo.lock',
    'src-tauri/build.rs','src-tauri/tauri.conf.json','src-tauri/tauri.release.conf.json',
    'src-tauri/capabilities','src-tauri/src','src-tauri/icons','src-tauri/binaries/.gitkeep'
]


def run(*args: str, capture=False, check=True):
    return subprocess.run(list(args),cwd=ROOT,check=check,text=True,encoding='utf-8',
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def check_staged_paths(paths):
    allowed={str(p) for p in PUBLIC_PATHS}
    for name in paths:
        path=Path(name);suffix=path.suffix.lower()
        if not any(name==prefix or name.startswith(prefix+'/') for prefix in allowed):
            raise RuntimeError('Refusing to publish an unexpected staged path: '+name)
        if (suffix in {'.sqlite','.db','.onnx','.heic','.heif','.jpg','.jpeg','.mp4','.mov','.mkv','.mp3','.wav'}
            or name.startswith('models/') and name!='models/manifest.json'
            or any(part in {'YoreviaVault','private-data','originals','exports','__pycache__','.venv','node_modules'} for part in path.parts)
            or '.sqlite-' in name or path.name.startswith('.env')):
            raise RuntimeError('Possible private/generated data in staging; stopped: '+name)
        if suffix in {'.png','.ico','.icns'} and not name.startswith(('src-tauri/icons/','docs/screenshots/')):
            raise RuntimeError('Only project icons and documented synthetic screenshots may be published: '+name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',default='Eronwu/Yorevia',help='owner/repository')
    parser.add_argument('--visibility',choices=['public','private'],default='public')
    parser.add_argument('--build',action='store_true',help='Dispatch native package CI after a successful push')
    parser.add_argument('--dry-run',action='store_true',help='Show intended steps without modifying local/GitHub state')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):
        parser.error('--repo must be owner/repository')
    if args.dry_run:
        print('Project:',ROOT)
        print('1. Verify gh authentication and repository ownership: '+args.repo)
        print('2. Initialize this folder only, stage explicitly allowed project files, commit if changed.')
        print('3. Create the repository only if not found; visibility for a NEW repository: '+args.visibility)
        print('4. Add a matching origin if missing; ordinary push, never force.')
        if args.build:print('5. Dispatch desktop.yml; it builds native targets on GitHub, not on this machine.')
        print('No files or remote repositories have been changed.')
        return
    for tool in ('git','gh'):
        if not shutil.which(tool):
            raise RuntimeError(tool+' is required. Install Git and GitHub CLI; then run gh auth login.')
    run('gh','auth','status')
    profile=json.loads(run('gh','api','user',capture=True).stdout)
    if profile['login'].lower()!=args.repo.split('/')[0].lower():
        raise RuntimeError('Authenticated account does not match the requested owner. Use the intended account first.')
    remote_url='https://github.com/'+args.repo+'.git'
    if not (ROOT/'.git').exists():
        parent=run('git','rev-parse','--show-toplevel',capture=True,check=False)
        if parent.returncode==0:
            raise RuntimeError('This folder is inside another Git repository. Extract the source into a separate folder first.')
        run('git','init','--initial-branch=main')
    actual=Path(run('git','rev-parse','--show-toplevel',capture=True).stdout.strip()).resolve()
    if actual!=ROOT:
        raise RuntimeError('Refusing to operate on a parent or unrelated repository.')
    origin=run('git','remote','get-url','origin',capture=True,check=False)
    if origin.returncode==0:
        normalized=origin.stdout.strip().removesuffix('.git')
        if normalized not in {'https://github.com/'+args.repo,'git@github.com:'+args.repo}:
            raise RuntimeError('origin points elsewhere; no remote settings were changed.')
    identity=run('git','var','GIT_AUTHOR_IDENT',capture=True,check=False)
    if identity.returncode:
        run('git','config','--local','user.name',profile.get('name') or profile['login'])
        run('git','config','--local','user.email',f"{profile['id']}+{profile['login']}@users.noreply.github.com")
        print('Configured commit identity locally in this project only (GitHub no-reply address).')
    selected=[p for p in PUBLIC_PATHS if (ROOT/p).exists()]
    run('git','add','--',*selected)
    staged=run('git','diff','--cached','--name-only','--diff-filter=ACMR',capture=True).stdout.splitlines()
    check_staged_paths(staged)
    changed=run('git','diff','--cached','--quiet',check=False).returncode
    if changed==1:run('git','commit','-m','feat: bootstrap Yorevia local-first desktop alpha')
    elif changed!=0:raise RuntimeError('Unable to inspect staged changes.')
    branch=run('git','branch','--show-current',capture=True).stdout.strip()
    if not branch:raise RuntimeError('Detached HEAD: switch to a branch before publishing.')
    existing=run('gh','api','repos/'+args.repo,capture=True,check=False)
    if existing.returncode:
        if '404' not in existing.stderr and 'Not Found' not in existing.stderr:
            raise RuntimeError('Cannot verify repository state: '+existing.stderr.strip())
        run('gh','repo','create',args.repo,'--'+args.visibility,'--description',
            'A local-first life atlas connecting photos, people and stories across time. Alpha.')
    if origin.returncode!=0:run('git','remote','add','origin',remote_url)
    # Per-command credential helper: no global config changes and no token handling.
    run('git','-c','credential.https://github.com.helper=',
        '-c','credential.https://github.com.helper=!gh auth git-credential','push','-u','origin',branch)
    print('Pushed to https://github.com/'+args.repo+' on '+branch)
    if args.build:
        run('gh','workflow','run','desktop.yml','--repo',args.repo,'--ref',branch)
        print('Build requested. Inspect results with: gh run list --repo '+args.repo+' --workflow desktop.yml')
        print('A dispatched build is not proof of a successful or signed installer.')

if __name__=='__main__':
    try:main()
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        print('Stopped safely:',exc,file=sys.stderr)
        sys.exit(1)
