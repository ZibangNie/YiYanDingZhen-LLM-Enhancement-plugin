# 安全说明

## 报告安全问题

请通过 GitHub Security Advisory 私下报告安全问题，不要在公开 Issue 中粘贴凭据、访问令牌、用户文档或可利用细节。

## 凭据

历史原型曾把百度 / 文心一言凭据写入源码和本地 Git 历史。这些凭据必须按已泄露处理并在百度控制台吊销或轮换。新代码只从 `QIANFAN_API_KEY` 或兼容别名读取千帆 v2 Bearer API Key，旧 Secret 不再使用。

禁止提交：

- `.env`
- API Key、Secret、Access Token
- 用户上传的原始文档
- 包含模型对象的 pickle

## 本地资产

Python pickle 可以在加载时执行代码。`scripts/migrate_legacy_index.py` 只用于迁移由项目所有者确认可信的历史本地索引；不要对下载文件或第三方文件运行它。

运行时索引使用 `index.annoy` 和 JSON 文档映射，并可通过 `artifacts/manifest.json` 中的 SHA-256 校验。

千帆客户端不会把 API Key 写入对象表示或错误消息；上游错误只返回 HTTP 状态和可用的请求 ID。

## 网络边界

远程文档接口默认：

- 仅接受 HTTP(S)，并默认只启用 HTTPS
- 拒绝回环、私网、链路本地、保留和云元数据地址
- 每次重定向后重新校验目标
- 设置连接 / 读取超时与最大响应大小

生产部署还应增加身份认证、速率限制、请求审计和反向代理层。

依赖更新由 CI 中的 `pip-audit` 和 Dependabot 辅助检查。安全审计不能替代对模型输入、知识库授权和生产部署边界的人工评审。
