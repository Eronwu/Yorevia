#!/usr/bin/env python3
"""Start or reuse the same loopback Yorevia Web service and open its browser tab."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import webbrowser

from local_web_settings import LocalWebSettings, default_profile

PORT = 4173
HOST = '127.0.0.1'
URL = f'http://{HOST}:{PORT}'
SERVER = Path(__file__).resolve().with_name('preview.py')


def service_ready() -> bool:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=.4)
    try:
        conn.request('GET', '/health')
        response = conn.getresponse()
        return response.status == 200 and json.loads(response.read(1024)) == {
            'service':'yorevia-local-web', 'protocol':1,
        }
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def desktop_exec(arguments: list[str]) -> str:
    # First apply Desktop Entry Exec quoting; then escape backslashes for
    # Desktop Entry values (a separate parsing layer). Always double % codes.
    def escape(item):
        quoted = ''.join('\\' + c if c in '\\"$`' else c for c in item)
        return '"' + quoted.replace('\\','\\\\').replace('%','%%') + '"'
    if any(any(c in item for c in '\r\n\x00') for item in arguments):
        raise ValueError('The installation paths cannot contain line breaks.')
    return ' '.join(map(escape, arguments))


def linux_desktop_entry(background: bool) -> str:
    args = [sys.executable, str(Path(__file__).resolve())]
    if background:
        args.append('--no-browser')
    return ('[Desktop Entry]\nType=Application\n'
            'Name=Yorevia Web\nComment=Open the local Yorevia browser interface\n'
            f'Exec={desktop_exec(args)}\nTerminal=false\nCategories=Utility;\n')


def install_linux_shortcuts(autostart: bool) -> None:
    if not sys.platform.startswith('linux'):
        raise ValueError('This shortcut installer is for Linux desktop environments.')
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    entries = [(data / 'applications/yorevia-web.desktop', False)]
    if autostart:
        entries.append((config / 'autostart/yorevia-web.desktop', True))
    for entry, background in entries:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(linux_desktop_entry(background), encoding='utf-8')
        print(entry)


def launch(no_browser: bool) -> None:
    if not service_ready():
        profile = LocalWebSettings(default_profile()).profile
        log = profile / 'launcher.log'
        command = [sys.executable, str(SERVER), '--local-web', '--no-open']
        # The profile and its assets are per-user. No elevated daemon is needed.
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(log, flags, 0o600), 'ab') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                     start_new_session=True)
        # First start may spend time importing native image/media dependencies.
        deadline = time.monotonic() + 45
        while not service_ready():
            if time.monotonic() > deadline or child.poll() is not None:
                # One more check for a concurrent click that already started it.
                if service_ready():
                    break
                raise ValueError('Yorevia Web could not start. Check the launcher log and whether port 4173 is in use.')
            time.sleep(.15)
    if not no_browser and not webbrowser.open(URL):
        raise ValueError(f'Yorevia is running. Open {URL} in your browser.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--install-linux-shortcut', action='store_true')
    parser.add_argument('--autostart', action='store_true', help='Optional desktop-login startup for the installed shortcut.')
    args = parser.parse_args()
    if args.autostart and not args.install_linux_shortcut:
        parser.error('--autostart requires --install-linux-shortcut')
    try:
        if args.install_linux_shortcut:
            install_linux_shortcuts(args.autostart)
        else:
            launch(args.no_browser)
    except (OSError, ValueError) as exc:
        if sys.platform.startswith('linux') and os.environ.get('DISPLAY') and not (args.no_browser or args.install_linux_shortcut):
            # .desktop launch lacks a terminal; make startup errors visible.
            subprocess.run([sys.executable, str(SERVER.with_name('local_web_picker.py')), '--error', str(exc)], check=False)
        raise SystemExit(str(exc))


if __name__ == '__main__':
    main()
