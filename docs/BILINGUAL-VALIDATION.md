# Bilingual interface verification — 2026-11-19

The app uses local TypeScript dictionaries, with System / 简体中文 / English selectors on welcome and settings. Chinese system languages resolve to Simplified Chinese; other languages fall back to English. An explicit selection is stored in this app's localStorage. If storage is blocked, it remains a session-only preference. No remote translation, telemetry, account, migration or content rewriting is involved.

Static interface labels, native folder-dialog titles and known application errors are localized. Unknown OS/library diagnostics and raw task reports remain verbatim. Progress labels that can be filenames remain verbatim. Existing open dialogs preserve their form fields and authorization sessions on system-language changes; their labels update the next time they open. User names, stories, file names, paths and fictional demo content remain in their original language. HTML storybook chrome follows the selected language; Markdown/JSON records remain unchanged.

## Checks run locally (Linux)
- TypeScript check and production build: passed.
- Node frontend/i18n tests: 13 passed, including dictionary completeness, interpolation tokens, storage-failure fallback and unchanged user names.
- Python suite: 80 passed, including both export locales, invalid locale fallback, unchanged user content and HTML escaping.
- Standalone offline bundle generation and JavaScript syntax: passed.
- Chromium UI smoke: blocked before page creation by this executor's `socket() failed: Operation not permitted`, also on the permitted elevated retry. This is not a UI pass.

`python scripts/check_i18n_browser.py` supplies a synthetic-data browser regression for saved preference/reload, system changes during an unsaved story, import, navigation, export, repeated Baidu modal entry and responsive English layout. The PR's Ubuntu browser CI runs this test; core CI separately covers Linux, macOS and Windows. Check the exact PR commit's workflow results rather than assuming these checks passed.

No macOS or Windows desktop installer for these changes has been built or manually launched here. Earlier native-validation documents concern earlier commits, not this localization change. Native WebView preference persistence, platform dialog appearance and real-device layout still require platform validation. This branch is a draft review, not a release or merge.
