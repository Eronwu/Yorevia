# Yorevia

**A private atlas of your life.**

[中文](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Latest native validation](docs/NATIVE-VALIDATION-2026-11-15.md)

Yorevia connects existing photos, videos and text files to a life timeline, locally grouped people, explicit relationships and handwritten stories. Originals remain in place. No account, hosted data store, telemetry, remote fonts or runtime model downloads.

**Version 0.1.0-alpha.1 remains an unsigned engineering preview, not a fully accepted release.** As of 2026-11-15, source is synchronized to [Eronwu/Yorevia](https://github.com/Eronwu/Yorevia) and [native CI](https://github.com/Eronwu/Yorevia/actions/runs/43706954518) passed for Apple Silicon, Intel macOS and Windows x64. Official YuNet/SFace weights were hash-verified and exercised with synthetic inputs; real-person recognition and cross-age accuracy remain unvalidated. Physical Apple Silicon testing verified launch, the native folder picker, vault creation, Chinese story save/readback and persistence after restarting. See the [native validation record](docs/NATIVE-VALIDATION-2026-11-15.md).

The project contains a Tauri 2 desktop shell, a dependency-free TypeScript UI, a Python/SQLite indexer, YuNet/SFace integration, human corrections through merge/split, a time-filtered co-occurrence graph, user-authored time-bounded relationships, and Markdown/JSON/HTML exports. Merge/split is manual; there is no one-click undo history yet.

## Develop

Use Python 3.12, Node 22 and a virtual environment.

```sh
python -m pip install -r requirements-dev.txt
npm install
npm run build
python -m pytest -q
npm test
python scripts/preview.py
```

The developer server binds loopback only and must not be exposed publicly. Desktop mode uses a private stdin/stdout sidecar protocol rather than a listening HTTP server.

For explicit model preparation, run `python scripts/fetch_models.py`. This downloads official weights, verifies fixed hashes, and preserves upstream licences. Face analysis is opt-in and runs locally. No external identity search or sensitive-attribute classification is performed.

For native builds, install Rust and OS toolchains, then follow [BUILD.md](docs/BUILD.md). Workflows cover Apple Silicon, Intel macOS and Windows x64. Packages are unsigned alpha builds until signing/notarization and platform acceptance are completed.

## Native package status

| Target | CI and package | Physical-device acceptance |
|---|---|---|
| macOS Apple Silicon | Passed; app / DMG | Basic startup, native IPC, story save and restart persistence passed |
| macOS Intel | Passed; app / DMG | Pending |
| Windows x64 | Passed; NSIS EXE | Pending |

[Download CI artifacts](https://github.com/Eronwu/Yorevia/actions/runs/43706954518) (GitHub login required; expire 2026-11-29). Packages correspond to code commit `3a852e4`; no formal release has been published. Bundled Python engine/model smoke tests passed on all targets. End users do not need a separate Python installation.

Packages are not formally signed or notarized. macOS has only a linker-generated adhoc signature and fails complete `codesign --verify --deep --strict` resource verification; this is not Developer ID signing or Apple notarization. Windows is unsigned. Full photo-import/export workflows, recognition accuracy and large-library performance still require physical-device acceptance. Windows ARM64 is not covered.

## Ownership and limitations

The local SQLite database is authoritative; portable exports are readable snapshots, not restorable full backups. Keep active vaults on a local disk and back up only after closing the application. The vault is **not encrypted**. All source media, names, face vectors and written stories remain sensitive. A missing person in later photos is not evidence that a relationship ended.

The supplied single-file visual demo uses fictional data and original abstract artwork. It cannot import files and is not the desktop application.

Source licence: Apache-2.0. Third-party model/runtime/codec licences are separate; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
