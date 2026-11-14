# 这份交付怎么用

本次提供的是可运行的 **V0.1 Alpha 源码工程**，不是已经签名验证的 Mac / Windows 安装程序。

1. 先打开根目录 `Yorevia-visual-demo.html`，看无需安装依赖的只读界面示例。它不会扫描私人文件。
2. 阅读 `README.md`，按开发预览步骤运行真正的文件索引/故事功能；源码 ZIP 附带已编译 `dist/`，无需为第一次浏览预览重建前端。
3. 真实人脸识别需显式准备两个经过校验的 OpenCV 模型；本次没有把未经验证的模型放入交付包。
4. 在有 Git/gh 登录权限的机器运行 `scripts/publish_github.py --repo Eronwu/Yorevia --visibility public --build`，完成实际远端同步并启动三目标 CI。脚本未在本次环境执行远端写入。
5. 不要以“CI 已配置”替代“安装包已成功构建”；查看实际 jobs 和 artifacts，再做真机验收。

`docs/VALIDATION.md` 逐项区分已测试和未测试。本项目的导出不是完整备份；资料库必须在关闭应用后连同原件一起妥善备份。

若另有 `.bundle` 文件，它是本地 Git 提交归档，可用 `git clone Yorevia-v0.1.0-alpha.1.bundle Yorevia` 恢复源码历史；它不是已经推送到 GitHub 的证明，也不含未跟踪的 `dist/` 和单页示例。
