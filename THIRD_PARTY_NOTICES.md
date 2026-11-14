# 第三方组件与模型说明

Yorevia 自有源码使用 Apache-2.0；这不替换依赖自身的许可。此清单是工程预览阶段的归属说明，**不是最终安装包完整许可证审计或法律意见**。

| 组件 | 用途 | 上游来源 / 许可说明 |
|---|---|---|
| Tauri / Tauri dialog | 原生壳、目录选择 | https://github.com/tauri-apps/tauri / https://github.com/tauri-apps/plugins-workspace ，按实际下载版本保留 MIT/Apache 许可 |
| TypeScript | 前端编译 | https://github.com/microsoft/TypeScript ，Apache-2.0 |
| Python | 本地引擎 | https://www.python.org/ ，PSF 及所含组件许可 |
| NumPy | 特征计算 | https://github.com/numpy/numpy ，BSD 及所带数学库许可 |
| Pillow | 元数据、图像 | https://github.com/python-pillow/Pillow ，HPND 及其二进制包含组件许可 |
| OpenCV Python | 检测、特征、视频首帧 | https://github.com/opencv/opencv-python ，包装与 OpenCV/附带编解码器分别适用许可 |
| pillow-heif / libheif | 可选 HEIC 解码 | https://github.com/bigcat88/pillow_heif ，必须另核对 libheif 与 wheel 内部编解码器及平台依赖 |
| PyInstaller | sidecar 打包 | https://github.com/pyinstaller/pyinstaller ，GPL + bootloader 分发例外，见上游实际版本 |
| SQLite | 本地结构化保存 | https://www.sqlite.org/copyright.html ，公共领域声明 |

## 模型不是源码许可证的自动延伸

`models/manifest.json` 指定模型文件、官方来源、SHA-256 和许可 URL。下载脚本保留上游原文为 `*.onnx.LICENSE`；打包时一并携带。没有校验通过的模型和许可文件时，sidecar 构建会停止。

- YuNet `face_detection_yunet_2023mar.onnx`：OpenCV Zoo 对应模型目录 MIT 许可。
- SFace `face_recognition_sface_2021dec.onnx`：OpenCV Zoo 对应模型目录 Apache-2.0 许可。

模型代码/权重许可、训练数据权利、使用者处理照片的授权，以及特定地区的商用/生物识别规定是不同问题。代码库不做“所有场景商用安全”的保证。

## 安装包发布前的额外要求

PyInstaller 可能打入原生库及其间接依赖。发布前必须对实际产物生成软件物料清单、保留完整许可文本，核验 HEIF/视频编解码器与平台二进制，不仅检查 Python 顶层包的许可证。尚未产出 native 包，因此本次未完成这一审计。

界面使用系统字体，不捆绑或再分发字体文件。演示的抽象景物图案与应用图标为本项目生成的原创代码绘图；演示人物是虚构文字标签，不含真人照片。
