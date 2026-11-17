# Baidu developer source: native build validation, 2026-11-17

Source commit: `272e8c6890ef64e523faff5c786a8b6c67f5b7fb`

Build: <https://github.com/Eronwu/Yorevia/actions/runs/44086014871>

All three native jobs succeeded: Apple Silicon macOS, Intel macOS and Windows
x64. The pipeline includes TypeScript compilation, 8 frontend tests, Python
core and real-model tests, packaged-engine smoke tests, Rust command-boundary
tests and installer packaging. This manual workflow did not publish a Release.

## Artifacts

GitHub login is required for artifact downloads. These are unsigned Alpha
packages, not consumer-ready signed releases.

- [Apple Silicon Mac](https://github.com/Eronwu/Yorevia/actions/runs/44086014871/artifacts/14329867081), expires 2026-12-01 12:48:48 UTC.
- [Intel Mac](https://github.com/Eronwu/Yorevia/actions/runs/44086014871/artifacts/14330775158), expires 2026-12-01 12:53:04 UTC.
- [Windows x64](https://github.com/Eronwu/Yorevia/actions/runs/44086014871/artifacts/14328837918), expires 2026-12-01 12:49:11 UTC.

## Apple Silicon physical-Mac checks

The entire artifact ZIP passed CRC verification, and the contained DMG passed
`hdiutil verify`. Both main executable and bundled engine are arm64 Mach-O.
The application was launched directly from the newly downloaded, read-only DMG.
No Gatekeeper or system-security setting was changed.

Verified in the native `tauri://localhost` WebView:

1. Create an isolated vault through the native folder picker.
2. Enter Baidu from the top-bar source picker. The developer Access Token form
   appears instead of hanging at the loading screen.
3. Close it and reopen Baidu from Settings. The form remains usable.
4. Submit a deliberately invalid one-character test value. It is rejected;
   the UI currently displays the generic error `网盘请求失败`.
5. Import a newly created fictional local TXT file via the source picker.
   The task reports one item added and no errors. Its timeline entry and exact
   fictional content are readable, and the filename-derived date is labelled
   as an inference.

No private photos, real access token, application SecretKey or SignKey were
used. No real Baidu account was connected; live authorization, cloud browsing
and cloud download permissions have **not** been validated by this check.

DMG SHA-256:
`7bdf0e42e7067e6cba0013a55a2f7ed5d659cab1309c718770a0a402fb553987`

## Remaining limitations

- The app is not notarized. `codesign --verify --deep --strict` still reports
  `code has no resources but signature indicates they must be present`.
  Successful launch on this test Mac does not establish frictionless or safe
  consumer distribution on other Macs.
- Windows and Intel builds passed CI, but no physical-device installation was
  performed for them.
- The Baidu feature is a session-token developer preview, not public OAuth
  sign-in. See [integration boundaries](BAIDU-NETDISK.md).
- Native invalid-input errors are currently generic; more actionable error
  display is a UI improvement still outstanding.
- The older core-only workflow 43916265391 ended with Windows/Ubuntu success
  and a cancelled macOS job. It must not be described as a three-platform pass.
  The newer full desktop workflow above succeeded on all three target platforms.

This document-only follow-up does not change the binaries or their source
commit. A new main-branch core test run does not rebuild the installer artifacts.
