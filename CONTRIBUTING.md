# 参与 Yorevia

先读 README、架构、隐私边界与验证记录。优先补充缺失的真实平台/模型验收，而不是增加未经验证的宣传功能。

## 本地检查

```sh
python -m pip install -r requirements-dev.txt
npm install
npm run check
npm run build
npm test
python -m pytest -q
```

浏览器 smoke 额外需要 Playwright 和 Chromium；它模拟原生 IPC，使用真实 Python 服务，不代表 Tauri 经过真机验证。模型 smoke 需要校验通过的模型文件。不能因缺少模型而把 skip 写成 pass。

## 提交约定

- 不提交原件、用户故事、真实照片、人脸特征、数据库、访问令牌和已下载模型。
- 演示资料必须虚构或有清晰再分发授权；代码库截图目前仅含虚构示例。
- 人物、关系与故事数据迁移必须有测试；人工确认信息不得被重扫覆盖。
- UI 读取的路径不得直接绕过原生目录授权。避免开放通用 shell / 任意文件读取接口。
- 不把同框次数解释为关系亲疏，不把缺少照片解释为关系结束。
- 模型变化记录上游来源、固定校验值、许可、实际效果与回滚方案。
- 小步提交，关联可复现问题；不要为赶进度关闭测试或伪造 native build 状态。

当前前端为严格 TypeScript + DOM/SVG。可讨论 React/D3 迁移，但避免同时重写持久化层和 UI。
