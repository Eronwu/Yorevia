# Yorevia Web (local engineering preview)

This is a browser interface for the on-device Yorevia engine, **not a hosted site**. The active service only listens on `127.0.0.1:4173`. It does not expose a LAN or Internet URL. Choose a folder through the operating system dialog the first time. A later service launch reopens the same vault if its existing files are available. If the drive is missing or the desktop app holds the vault, it does not silently create a replacement. The desktop edition and Web edition should not be used concurrently on the same vault.

The user's sources and SQLite data stay on the computer that runs the local service. A VM demo should only use synthetic files. The private Web profile remembers the vault directory, not passwords or cloud tokens. The vault itself is **not encrypted**.

## Linux desktop setup (once)

From a checkout or extracted source bundle in a permanent directory, install Python 3.12, a desktop GUI with Tk, and Node as described in the project README. Prepare the dedicated runtime and build the browser assets once:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build
.venv/bin/python scripts/launch_local_web.py --install-linux-shortcut
```

If a bundle already contains `dist/`, the Node steps are optional for running that bundle. Preserve the checkout/installation location and virtual environment so the shortcut remains valid. The shortcut contains no private data or tokens. To opt into starting the service when signing in to the desktop (without opening a browser), add `--autostart` when installing the shortcut. This step is optional and does not need administrator access.

**Daily use:** click **Yorevia Web** in the application menu. It starts the local service if needed and opens `http://127.0.0.1:4173` in your normal browser. With login startup, opening the bookmarked address works directly. No daily terminal command is needed. Closing the tab does not stop the background service. To stop starting it on login, remove the `yorevia-web.desktop` entry under your XDG config directory's `autostart/` folder. Stop the existing process from the system monitor if you need to release the vault before opening it in desktop Yorevia.

To test the service directly on a separate profile, use `python scripts/preview.py --local-web --profile /absolute/path/to/private-profile --port 0 --no-open` and browse the address printed. Never port-forward this profile or reuse a real vault for a development test. The default developer-preview workflow has not been changed.

## Platform limits

The Linux shortcut and browser workflow are the target of this preview. The Web server and macOS chooser path are portable source, not an installed or signed macOS application. A macOS click-to-start or sign-in launcher, macOS Keychain carryover, Safari acceptance, Windows shortcuts and existing personal vault/real Baidu account acceptance require separate validation. The preview neither migrates credentials nor uses the cloud computer as a data host.

## Baidu in this preview

An authenticated Baidu session can recursively index supported cloud photos under the selected directory. Scanning requests the listing only; it does not request original files or use a local downloads folder. The timeline requests smaller previews when needed and the detail view requests a larger rendition when available. Both are cached temporarily in memory. Missing or unavailable renditions show a retry/reconnect path; originals are not silently substituted. Dates without evidence remain unknown. This preview does not persist Baidu sign-in, and cannot carry over the desktop app's Keychain session. A simulated provider was used in Cloud QA; production Baidu rendition coverage was not measured.
