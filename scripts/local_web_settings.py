"""Private profile and native folder consent for the loopback UI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time


PICK_TITLES = {
    'vault.open': {'en':'Choose the Yorevia vault folder','zh-CN':'选择人生资料库目录'},
    'source.add': {'en':'Choose a source folder to index','zh-CN':'选择要索引的原始资料目录'},
    'baidu.import': {'en':'Choose where to save selected Baidu files','zh-CN':'选择所选网盘文件的本地保存目录'},
}
PATH_KEYS = {'vault.open':'path', 'source.add':'path', 'baidu.import':'destination'}
PICK_SCRIPT = Path(__file__).with_name('local_web_picker.py')


def default_profile() -> Path:
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Yorevia Web'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Yorevia Web'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'yorevia-web'


class LocalWebSettings:
    def __init__(self, profile: Path, picker=None):
        self.profile = profile.expanduser().absolute()
        self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.profile.is_symlink() or not self.profile.is_dir():
            raise ValueError('Invalid profile directory.')
        if os.name != 'nt':
            st = self.profile.stat()
            if st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise ValueError('The Yorevia Web profile must be private to the current account.')
        self.settings = self.profile / 'settings.json'
        self._picker = picker or self.pick_native
        self._picker_lock = threading.Lock()
        self._tickets = {}
        self._ticket_lock = threading.Lock()
        self.startup_error = False

    def saved_vault(self) -> Path | None:
        if self.settings.is_symlink() or (self.settings.exists() and not self.settings.is_file()):
            raise ValueError('Yorevia Web settings must be a regular file.')
        try:
            with self.settings.open(encoding='utf-8') as file:
                raw = json.loads(file.read(16_384))
        except FileNotFoundError:
            return None
        if not isinstance(raw, dict) or raw.get('version') != 1 or not isinstance(raw.get('vault'), str):
            raise ValueError('Invalid Yorevia Web settings.')
        candidate = Path(raw['vault'])
        if not candidate.is_absolute() or candidate.resolve(strict=True) != candidate:
            raise ValueError('The saved vault directory is no longer available at its original location.')
        for name in ('vault.json', 'vault.sqlite'):
            path = candidate / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('The saved vault is offline or incomplete; it was not recreated.')
        return candidate

    def remember(self, vault: str) -> None:
        fd, temp = tempfile.mkstemp(prefix='.settings-', dir=self.profile)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump({'version':1, 'vault':vault}, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.settings)
        finally:
            Path(temp).unlink(missing_ok=True)

    @staticmethod
    def pick_native(purpose: str, locale: str) -> str | None:
        title = PICK_TITLES[purpose]['zh-CN' if locale == 'zh-CN' else 'en']
        result = subprocess.run([sys.executable, str(PICK_SCRIPT), title],
                                capture_output=True, text=True, timeout=300, check=False)
        if result.returncode:
            raise ValueError('The system folder picker did not open. Start Yorevia from the desktop and try again.')
        value = json.loads(result.stdout)
        if value is not None and not isinstance(value, str):
            raise ValueError('Invalid folder selection.')
        return value

    def pick(self, purpose: str, locale: str) -> str | None:
        if not isinstance(purpose, str) or purpose not in PATH_KEYS or not self._picker_lock.acquire(blocking=False):
            raise ValueError('Folder selection unavailable or already in progress.')
        try:
            selected = self._picker(purpose, locale)
            if selected is None:
                return None
            path = Path(selected).resolve(strict=True)
            if not path.is_dir() or path.parent == path:
                raise ValueError('Select a folder, not the entire disk.')
            now = time.monotonic()
            with self._ticket_lock:
                self._tickets = {k: v for k, v in self._tickets.items() if v[2] > now}
                if len(self._tickets) >= 8:
                    self._tickets.pop(next(iter(self._tickets)))
                ticket = secrets.token_urlsafe(32)
                self._tickets[ticket] = (purpose, path, now + 120)
            return ticket
        finally:
            self._picker_lock.release()

    def authorized_params(self, method: str, params: dict) -> dict:
        key = PATH_KEYS.get(method)
        if key is None:
            return params
        ticket = params.get(key)
        with self._ticket_lock:
            grant = self._tickets.pop(ticket, None) if isinstance(ticket, str) else None
        if grant is None or grant[0] != method or grant[2] < time.monotonic():
            raise ValueError('Please select the folder in the system dialog first.')
        path = grant[1]
        if not path.is_dir() or path.resolve(strict=True) != path:
            raise ValueError('The selected folder moved or is no longer available.')
        if method == 'vault.open':
            # Preserve the path from the dialog even if an intermediate
            # YoreviaVault child already exists.
            marker = path / 'vault.json'
            child = path / 'YoreviaVault'
            if marker.is_symlink() or (not marker.is_file() and child.is_symlink()):
                raise ValueError('Select the real vault folder, not a linked vault.')
        return {**params, key:str(path)}
