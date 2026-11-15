# Native alpha validation, 2026-11-15

Build: https://github.com/Eronwu/Yorevia/actions/runs/43706954518
Source: 3a852e432f30d7fe5bd36723728d128950a176b3

All three native jobs passed: Apple Silicon macOS, Intel macOS, Windows x64.
Each passed frontend tests, Python core/model tests, bundled Python engine smoke,
Rust command-boundary tests, installer packaging and artifact upload.
This manual run did not publish a GitHub release. Artifacts expire 2026-11-29.

## Apple Silicon physical Mac smoke
Downloaded the CI DMG, verified its filesystem checksum and inspected arm64
Mach-O main executable and bundled engine. Launched the app from the readonly
DMG without modifying system security settings. Native tauri://localhost
WebView rendered successfully. The packaged engine smoke returned installed
models and telemetry=false. Native folder picker created an isolated test vault.
A synthetic Chinese story was saved and read back in the story list.
After quitting and relaunching the app, reopening the same vault preserved
the story and its Chinese text. The app currently requires reselecting the vault.
No private photographs were imported or uploaded.

DMG SHA256:
9f664679feca76d0beee11362e00c8b616922b2e37c3ce733fc83e1c2dbc5604

An initial folder-picker selection had Open disabled; cancelling with Escape
and selecting a child test folder succeeded. A transient automation
noWindowsAvailable error was not an application crash (process remained alive).

## Limits
Unsigned alpha, not notarized. The main executable has a linker-generated adhoc
signature; codesign --verify --deep --strict reports an unsealed resource issue.
Do not present this as a signed or frictionless consumer distribution.
No Gatekeeper or other system-security bypass was performed.
Windows and Intel outputs passed CI but have not been manually installed on
physical machines. Full photo import, human-face accuracy, export and
large-library performance remain manual acceptance work.
The model test demonstrates real-weight plumbing, not recognition accuracy.
