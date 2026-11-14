# V0.1 Alpha 本次验证记录

日期：2026-11-14。范围：本次源码交付环境，不代表已发布 GitHub Release 或原生安装包。

## 实际执行并通过

| 检查 | 实际结果 |
|---|---|
| TypeScript 严格编译 `npm run build` | 成功生成 `dist/` |
| TypeScript 静态类型检查 `npm run check` | 通过 |
| Node 领域/转义/图谱布局测试 `npm test` | **7 passed，0 failed** |
| Python 测试 `python -m pytest -q` | **44 passed，1 skipped** |
| Python 语法编译 | `compileall` 通过 |
| 实际开发预览 HTTP 边界 | 合法令牌/Origin 请求通过；缺令牌、外来 Host/Origin 被拒绝；路径遍历被拒绝 |
| 浏览器 UI ↔ Python 服务 | 创建资料库、导入 3 份临时资料、2014 年筛选、保存有引用故事、转义恶意 HTML 字符串、导出 ZIP 全流程通过 |
| 浏览器错误与请求 | 上述内存载入测试 0 page errors、0 network requests |
| 可交互演示 | 时间轴 / 人物图谱 / 故事视图已渲染检查，截图在 `docs/screenshots/` |
| 配置文件 | JSON 与工作流 YAML 解析通过；这不等于 Tauri 配置 schema 已经由 native 构建验证 |
| GitHub 发布辅助脚本 | `--dry-run` 通过；路径允许/拒绝规则有自动测试，没有执行远端写入 |

### 测试覆盖的实质行为

原件只读；重复扫描去重；改名/移动后保留故事引用；同路径内容更改；离线磁盘与文件删除的区别；人工日期不被重扫覆盖；Unicode 和文字搜索；故事外键错误回滚；资料路径越界与符号链接；取消扫描；资料库重复打开锁；导出转义与敏感字段剔除；人物分组/年份过滤、同框不自动合并为同人、合并/拆分、人工关系时间范围；删除特征不删故事；模型匹配策略；RPC 持久进程；单张人像事务失败回滚；合并保留旧称呼与说明。

人像归类的领域测试使用 **FakeEngine 和人工构造向量**。它们验证数据流程，不测真实人脸模型效果，不能用来宣传“识别准确”。

### 浏览器测试边界

在 Linux Chromium 中以内存方式载入本项目 HTML/CSS/JS，通过模拟的 Tauri `invoke` 连接真实 Python `Service`，操作临时合成图片/文字。**原生目录选择器、Rust IPC、macOS WebKit、Windows WebView2 被模拟或未参与**，并非原生端到端验收。

没有读取用户照片；截图中的人物与人生记录为虚构演示。测试所需的临时库在结束后清理。

## 明确未完成

| 项目 | 状态 / 原因 |
|---|---|
| 官方 YuNet/SFace 真实推理 | 模型文件未安装；唯一 skipped 用例明确标记。没有下载校验通过的模型可运行。 |
| 人物识别准确率、跨年龄效果 | 未做真实授权照片集评测 |
| HEIC 实际解码 | optional decoder 未安装于本次环境；只写了依赖与代码路径 |
| Rust/Tauri 编译 | 当前环境无 Rust/native OS 工具链，未执行 |
| macOS ARM64、macOS x64、Windows x64 安装包 | 只有构建配置，无本次实际 DMG/EXE 产物 |
| 安装、启动、系统目录授权、原生 UI、卸载 | 未做双平台真机验收 |
| Apple 签名/公证、Windows 签名 | 未配置 |
| GitHub 同步 / Actions 实际构建 | 未执行。连接只提供读取；`Eronwu/Yorevia` 当前查询返回 404（可能不存在或不可见）。Mac 文件连接离线。 |
| 大资料库性能 / 断电恢复 / 安全审计 | 未做系统评测 |

## 环境记录

- Linux 开发容器，不是 macOS 或 Windows。
- Python 3.13.5；CI 计划使用 Python 3.12，仍需实际运行。
- Node 22.16.0；TypeScript 5.8.3。
- Pillow 12.3.0、NumPy 2.3.5、OpenCV 4.13.0、pytest 9.0.2。
- Playwright 1.57.0 + 系统 Chromium；界面无需远程字体或图片。

## 可复查命令

```sh
npm run build
npm run check
npm test
python -m pytest -q
python scripts/check_browser.py --chromium /usr/bin/chromium
python scripts/publish_github.py --dry-run --build
```

真实模型与 native build 的验收不得用上面的成功结果替代。发布阻断项见 `ROADMAP.md`。
