# 开发、Mac / Windows 构建与 GitHub 交付

> 历史构建记录：Yorevia 已改为本地网页版，停止独立 macOS / Windows 安装包 CI 与发布。当前使用方式见 [LOCAL-WEB.md](LOCAL-WEB.md)。以下旧桌面命令保留供追溯；相关发布工作流不再可运行。


**当前状态：构建配置已编写，本次没有产出或验证 DMG / EXE。** 以下是应执行的流程，不是已执行的记录。

## 1. 工具链

建议 Python 3.12、Node 22、Rust stable（至少 1.90）。macOS 需要 Xcode 命令行工具。Windows 需要 Rust MSVC 工具链、Visual Studio C++ Build Tools 和 WebView2 支持。使用 x64 Windows；Apple Silicon 与 Intel macOS 必须各自在原生 runner 构建 sidecar。

Tauri 官方前置条件：<https://v2.tauri.app/start/prerequisites/>

### macOS

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm install
python scripts/fetch_models.py
npm run build
npm test
python -m pytest -q
npm run desktop:dev
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm install
.venv\Scripts\python.exe scripts/fetch_models.py
npm run build
npm test
.venv\Scripts\python.exe -m pytest -q
npm run desktop:dev
```

Tauri 开发端自动优先查找项目 `.venv`。也可以设置 `YOREVIA_PYTHON` 为解释器完整路径。不要为了运行脚本关闭系统整体安全策略。

## 2. 在目标机器构建安装包

准备已校验的模型后，在上述虚拟环境中运行：

```sh
python scripts/make_icons.py
python scripts/build_sidecar.py
npx tauri build --config src-tauri/tauri.release.conf.json
```

Windows 不激活虚拟环境时，把 `python` 替换为 `.venv\Scripts\python.exe`。Python sidecar 打包检查 Rust host triple，不允许把当前主机二进制冒充另一平台产物。

构建输出位于 `src-tauri/target/release/bundle/`；使用 `--target` 时则在 `src-tauri/target/<target>/release/bundle/`。macOS 目标是 DMG + app，Windows CI 指定 `--bundles nsis`。

**签名状态：** 未配置 Apple Developer 签名、公证或 Windows 代码签名。操作系统可能拦截未签名 alpha。正式发行前需提供相应证书和 CI secrets，按官方流程配置并真机验证；本项目不会要求用户全局关闭 Gatekeeper 或 SmartScreen。

## 3. 同步 GitHub 并启动构建

当前聊天连接不能写 GitHub。随代码提供的脚本由你自己的本地 Git/gh 权限执行，不接触聊天中的凭证。

```sh
gh auth login
python scripts/publish_github.py --repo Eronwu/Yorevia --visibility public --build
```

需要当前登录用户是 `Eronwu`；脚本拒绝误推到其他账户。已有同源 Git 仓库会保留历史，非空远端冲突时普通 push 失败，不强推。源码 ZIP 没有 `.git`；脚本仅在当前项目文件夹初始化。

先检查计划而不修改任何状态：

```sh
python scripts/publish_github.py --repo Eronwu/Yorevia --visibility public --build --dry-run
```

成功推送后查看构建：

```sh
gh run list --repo Eronwu/Yorevia --workflow desktop.yml
gh run watch <run-id> --repo Eronwu/Yorevia
gh run download <run-id> --repo Eronwu/Yorevia --dir packages
```

新仓库工作流尚未登记、GitHub Actions 被账户策略禁用或权限不足时，命令可能失败。检查实际错误后可单独执行：

```sh
gh workflow run desktop.yml --ref main --repo Eronwu/Yorevia
```

“触发成功”不代表“构建成功”。必须检查每个 job 和实际 artifacts。

## 4. CI 的范围

`ci.yml`：三种 OS 的 Python 核心测试、TypeScript 编译、Node 领域测试；不带模型时明确跳过真实推理测试。

`desktop.yml`：Apple Silicon、Intel macOS、Windows x64 分别准备官方模型、强制执行模型 smoke、打包 Python sidecar、运行 sidecar smoke、Rust 单元测试、Tauri 安装包构建。不是人工 UI 或跨年龄识别准确率验证。成功的 artifacts 保留 14 天。

手动触发只产出构建 artifacts。推送 `v*` 标签会在三个目标全部成功后创建**草稿** prerelease，不自动公开。签名、公证、安装卸载、首次导入和恢复备份都需补验收。

当前未有实机生成的 `Cargo.lock` 和 `package-lock.json`。根 Python 依赖固定了版本，但完整传递依赖与 CI Action 仍未全部锁定。工作流会保存解析后的依赖记录；首次成功后应审计并提交锁文件、固定 Action SHA。**当前不能称为可复现发行版。**

## 5. 官方资料

- Tauri sidecar：<https://v2.tauri.app/develop/sidecar/>
- Tauri GitHub 分发：<https://v2.tauri.app/distribute/pipelines/github/>
- GitHub CLI 建仓：<https://cli.github.com/manual/gh_repo_create>
- GitHub CLI 工作流：<https://cli.github.com/manual/gh_workflow_run>
- GitHub 托管 runner：<https://github.com/actions/runner-images>
