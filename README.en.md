# Yorevia

**A private atlas of your life.**

[中文](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Validation](docs/VALIDATION.md)

Yorevia connects existing photos, videos and text files to a life timeline, locally grouped people, explicit relationships and handwritten stories. Originals remain in place. No account, hosted data store, telemetry, remote fonts or runtime model downloads.

**Version 0.1.0-alpha.1 is an engineering preview, not a verified native release.** The Python core and TypeScript interface have been tested in Linux; native macOS/Windows builds, real face-model execution and recognition accuracy were not verified in the delivery environment. Native build workflows are configured, not run. No GitHub synchronization is claimed.

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

## Ownership and limitations

The local SQLite database is authoritative; portable exports are readable snapshots, not restorable full backups. Keep active vaults on a local disk and back up only after closing the application. The vault is **not encrypted**. All source media, names, face vectors and written stories remain sensitive. A missing person in later photos is not evidence that a relationship ended.

The supplied single-file visual demo uses fictional data and original abstract artwork. It cannot import files and is not the desktop application.

Source licence: Apache-2.0. Third-party model/runtime/codec licences are separate; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
