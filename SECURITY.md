# 隐私与安全边界

Yorevia 当前是未完成发行验收的 Alpha。请先使用少量可备份、得到处理授权的资料验证，不要把它当作唯一档案备份。

## 默认数据行为

- 原始文件只读：索引、缩略图和人脸裁切写到用户选择的资料库。
- 桌面模式无 HTTP 服务；通过本地子进程的私有 stdin/stdout 交互。
- 无账号、遥测、远程字体、在线人脸检索、自动模型下载或远程地理编码。
- 人脸分析需要点击确认。模型只给出本地相似性分组，不给出真人身份，不分析敏感人口属性。
- 原始文件夹可自行在其他软件同步；这些软件的云上传策略不由 Yorevia 控制。

## 必须知道的限制

**本地并不等于加密。** SQLite、头像、缩略图和故事未加密；本机恶意软件、具有该账户权限的人或磁盘备份可能读取它们。应使用系统磁盘加密、合适账户权限和可信备份。

**不支持活动数据库的多端同步。** 将活动资料库放在网盘/NAS 并由多台机器打开可能损坏数据。进程锁只解决单机常规重复打开，不是跨设备协作锁。

**完整备份需先关闭应用。** 复制整个资料库，并另行备份原件。当前导出是便携阅读快照，不包含嵌入向量、原片和所有内部状态，也没有完整导入恢复功能。

**删除人像特征是逻辑删除。** 会删除记录和头像缓存，但不能保证 SSD、SQLite 历史页、系统快照、导出和旧备份中的物理擦除。人物名字、手写关系与故事会保留。

**媒体解码不是完整沙箱。** Pillow/OpenCV/HEIF 解码器处理不可信文件时仍可能出现资源耗尽或原生库问题。已有像素/文件尺寸限制、路径约束与错误报告，但尚未完成独立进程隔离和专业安全审计。

**文件移动不是所有变化。** 完整字节相同的文件可重连；修图、转码、清除元数据导致哈希变化，不保证能自动恢复关联。

**导出也敏感。** ZIP 不含原件、嵌入和绝对来源根路径/GPS，但保留姓名、故事、相对路径和预览图。请自行审阅，不能视为已经匿名化。

## 开发预览

`preview.py` 仅绑定 127.0.0.1，验证 Host、Origin 和随机请求令牌，阻止任意静态路径遍历。不提供身份账户或公网 TLS，不应使用端口转发公开访问。桌面版不启动这个开发服务。

## 报告问题

不要把私人照片、人脸嵌入、资料库或真实访问凭证放到公开 Issue。公开报告仅提供不含私人数据的复现步骤；敏感漏洞应使用仓库的私密漏洞报告功能（待维护者开启）。目前没有宣称已经运行的漏洞响应服务或安全认证。

## Optional Baidu developer source

Explicitly connecting Baidu accesses Baidu APIs/downloads directly and downloads only selected files into a dedicated local source directory. Session access tokens are not persisted. Do not submit app secrets, user tokens or private downloaded files to this repository. Public OAuth sign-in is not deployed. See [Baidu integration boundaries](docs/BAIDU-NETDISK.md).
