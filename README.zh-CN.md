<div align="center">

# Yorevia · 往途

**把散落的记忆，重新连成来时的路。**

Local-first · Open source · Your memories, your files

[English](README.md) · 简体中文 · [最新原生验证](docs/NATIVE-VALIDATION-2026-11-15.md) · [架构](docs/ARCHITECTURE.md) · [Mac / Windows 构建](docs/BUILD.md)

</div>

![Yorevia 人生长廊 — 虚构示例](docs/screenshots/timeline-demo.png)

> **0.1.0-alpha.1 / 工程预览，不是已验收的发行版。**
> 截至 2026-11-15，源码已同步到 [Eronwu/Yorevia](https://github.com/Eronwu/Yorevia)，[三平台原生 CI](https://github.com/Eronwu/Yorevia/actions/runs/43706954518) 已成功生成 Apple Silicon、Intel Mac 和 Windows x64 安装包。官方 YuNet / SFace 权重已校验并完成合成输入推理测试，**不代表真人识别或跨年龄准确率已验证**。Apple Silicon 真机已验证启动、原生目录选择、资料库创建、中文故事保存与重启后读回；Windows / Intel 真机安装及完整业务验收仍待完成。安装包为未正式签名、未公证的 Alpha，详见[本轮验证记录](docs/NATIVE-VALIDATION-2026-11-15.md)。

## 一个不要求你从空白页开始的人生档案

选择已有的照片、视频和文字文件夹，不搬迁原件，也不用注册账号。先看到自己的时间轴，再在某张旧照片唤起记忆时补上故事。

照片里的人在本机归类；名字由你填写。同框关系来自照片证据，“朋友”“同事”“家人”等真实关系由你确认，并可以记录起止日期。影像中没有再出现的人，不会被系统判定为已经离开你的生活。

### 此版本实现什么

| 功能 | 当前范围 |
|---|---|
| 人生长廊 | 年份筛选、月份分组、分页、标题/文字/故事搜索，未知日期单独显示 |
| 原件只读 | 本地文件夹及已下载的网盘同步目录；不改写、搬迁或删除原件 |
| 稳定关联 | 完整 SHA-256 内容标识；重复文件不重复建档，改名/移动后重新扫描可重连 |
| 时间来源 | EXIF 原始拍摄时间优先；文件名日期明确标记为推测；不把文件修改时间当成事件日期 |
| 同行的人 | YuNet + SFace 本地检测/特征/保守归类，命名、合并、单张人像拆分 |
| 时光人物图谱 | 随年份筛选人物，区分自动同框证据和人工真实关系；画布最多显示 24 人 |
| 故事手记 | 纯文字故事也可以存在；可绑定照片和人物；保留原文，不让模型自动改写 |
| 导出 | ZIP 内含 Markdown、JSON、缩略图和可离线阅读/打印的 HTML 故事册 |
| 隐私控制 | 不上传、不遥测、不自动下载模型；人像分析需确认；可以删除人脸特征和头像缓存 |

**不是本版能力：** 视频内人像识别、跨年龄准确识别保证、自动判断社交关系、面向普通用户的网盘一键登录、云同步冲突合并、地图、AI 传记生成、EPUB/Word 自动排版、加密资料库、已签名安装包。

## 先看界面，不读取任何私人资料

源代码交付 ZIP 附有 `Yorevia-visual-demo.html`，直接在浏览器打开。它使用本项目真实前端和明确标记的虚构示例数据，不包含真人照片，也不会访问你的文件。它是**只读视觉示例**，不是桌面应用。

从 Git 源码生成同一个示例：

```sh
npm install
npm run build
python scripts/make_standalone_demo.py
```

## 运行真实本地功能：开发预览

环境：Python 3.12（建议）、Node.js 22。交付 ZIP 已含 `dist/`；从 Git 拉取则需先编译前端。

```sh
python -m venv .venv
# macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run build
python scripts/preview.py
```

随后在页面选择或填写这台电脑上的目录：先创建资料库，再连接原始资料。开发预览只监听 `127.0.0.1`，带随机请求令牌与来源检查。**不要把该开发服务器转发到公网，也不要视为多用户服务。** 浏览器预览使用完整路径输入；桌面版本使用系统目录选择器。

PowerShell 无法激活虚拟环境时，无需修改全局安全策略，直接使用 `.venv\Scripts\python.exe -m pip install ...` 和 `.venv\Scripts\python.exe scripts/preview.py`。

### 开启真实本地人像分析

第一次准备源码开发环境时显式获取官方模型；运行中的应用不会下载或上传资料：

```sh
python scripts/fetch_models.py
```

脚本从 OpenCV 官方仓库下载两个模型，逐字节校验 SHA-256，并保留上游许可文件。下载需要网络；照片分析在本地完成。随后在应用中点击“开始本地人像分析”并确认。

不能联网的电脑可由另一台电脑运行上述脚本，再把完整 `models/` 复制过去。不要替换为来历不明的同名模型。模型未准备好时，时间轴与故事功能仍然可用。

## macOS / Windows 桌面工程

工程使用 **Tauri 2 + TypeScript 界面 + Python/OpenCV 本地引擎**。Alpha 前端没有 React 和远程资源依赖；这是为缩小初版依赖面而作的实现选择，见 [ADR-001](docs/ARCHITECTURE.md#adr-001-独立架构与运行时选择)。

2026-11-15 三种原生构建目标均已通过 CI（安装包代码提交：`3a852e4`）：

| 目标 | CI Runner | 产物 | 验证状态 |
|---|---|---|---|
| macOS Apple Silicon | `macos-15` | `.app` / `.dmg` | CI 通过；真机基础流程与故事重启持久化通过 |
| macOS Intel | `macos-15-intel` | `.app` / `.dmg` | CI 通过；真机安装验收待完成 |
| Windows x64 | `windows-2022` | NSIS `.exe` | CI 通过；真机安装验收待完成 |

安装包内已携带 Python 引擎与模型，三平台打包引擎 smoke 测试均通过，不要求最终使用者另装 Python。Windows ARM64 暂不在矩阵中。

[下载本轮 CI 安装包](https://github.com/Eronwu/Yorevia/actions/runs/43706954518)（需登录 GitHub；Artifacts 保留至 2026-11-29）。目前没有正式 Release。Mac 仅有 linker adhoc 签名，完整 `codesign --verify --deep --strict` 校验不通过；这不是开发者签名或 Apple 公证。Windows 同样未签名。完整照片导入、真人识别效果、导出和大资料库性能仍待真机验收。

## 同步到 GitHub

本仓库已完成源码同步；以下是后续维护或在新环境发布时使用的命令，不表示同步仍未完成。

先安装 Git、GitHub CLI，并用你自己的账户在本机登录。不要把访问令牌发到聊天或写入仓库。

```sh
gh auth login
python scripts/publish_github.py --repo Eronwu/Yorevia --visibility public --build
```

脚本会检查账号、仅暂存明确允许的项目文件、必要时新建仓库、普通推送并触发三平台构建。它不强制覆盖远端、不修改 Git 全局配置、不创建公开 Release。已有非空仓库发生历史冲突时会停止，而不是覆盖。

`--visibility` 仅用于新建仓库，不改变已有仓库的可见性。检查即将进行的步骤可先加 `--dry-run`。Windows 与 macOS 使用相同命令。

可选网盘功能请参阅[百度网盘开发者预览](docs/BAIDU-NETDISK.md)。

## 数据属于谁？

全部属于你。原件留在来源目录。你选定位置下的 `YoreviaVault/` 保存数据库、缩略图、人脸特征和故事。**它目前不是加密数据库**：能访问你的系统账户或磁盘的人可能读取这些内容。本地优先不等于绝对安全。

**不要把正在使用的 SQLite 资料库放到 NAS 或同步盘中由多台设备同时打开。** 原始资料可以位于可访问的文件夹；活动资料库应位于本机磁盘。关闭应用后再完整备份，或导出便携快照。不要仅复制仍在写入的 `vault.sqlite`。

当前 SQLite 是权威数据源，Markdown/JSON 是导出快照，不是双向同步数据库。导出包不含原片和人脸向量，但含私人故事、人物称呼和缩略图，仍须谨慎分享。详细边界见 [隐私与安全](SECURITY.md)。

## 验证与贡献

```sh
npm run build
npm test
python -m pytest -q
# 可选：已安装 Playwright 和 Chromium 后，执行真实界面 + Python 服务测试
python scripts/check_browser.py --chromium /path/to/chromium
```

真实模型测试缺少权重时会明确跳过；发布构建用 `YOREVIA_REQUIRE_MODELS=1` 强制要求模型可运行。测试中的伪造向量仅用于验证聚类流程，不表示真人识别效果。

阅读 [最新原生验证](docs/NATIVE-VALIDATION-2026-11-15.md)、[构建步骤](docs/BUILD.md)、[路线与验收标准](docs/ROADMAP.md) 和 [贡献说明](CONTRIBUTING.md)。

## 许可证

Yorevia 自有源码：Apache-2.0。第三方运行库、解码器和模型适用各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。开源代码许可不等于照片人物的隐私授权，也不等于所有模型/编解码器在所有地区的商业许可。
