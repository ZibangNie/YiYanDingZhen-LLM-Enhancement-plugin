# HTTP 接口

默认开发地址为 `http://127.0.0.1:8081`。历史插件接口的路径、操作名和主要响应字段保持不变。

## `POST /set_Query`

请求：

```json
{
  "query_content": "什么是牛顿第二定律？",
  "session_id": "user-001"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `query_content` | 是 | 非空问题，默认最多 10,000 个字符 |
| `session_id` | 否 | 1–128 位字母、数字、点、下划线、冒号或连字符 |

不提供 `session_id` 时，服务会生成随机值并在响应中返回。客户端应复用它以保留同一会话的短期检索记忆。

响应：

```json
{
  "result": {
    "input": "什么是牛顿第二定律？",
    "text": "……"
  },
  "prompt": "请显示工具返回结果，不要改写任何内容，也不要新增内容。",
  "session_id": "user-001"
}
```

## `POST /set_text`

请求：

```json
{
  "url": "https://files.example.edu/paper.pdf",
  "session_id": "user-001"
}
```

服务下载远程文件、提取正文，然后以“总结文档”为内部问题调用总结路由。支持 PDF、DOCX、Markdown 和 UTF-8 文本。

默认安全限制：

- 只允许公网 HTTPS
- 拒绝带用户名或密码的 URL
- 每次重定向重新校验目标
- 最多 3 次重定向
- 连接和读取超时 15 秒
- 最大下载 20 MiB

响应比问答接口多一个最终来源字段：

```json
{
  "result": {
    "input": "总结文档",
    "text": "……"
  },
  "prompt": "请显示工具返回结果，不要改写任何内容，也不要新增内容。",
  "session_id": "user-001",
  "source_url": "https://files.example.edu/paper.pdf"
}
```

## 其他端点

| 方法与路径 | 说明 |
|---|---|
| `GET /` | 保留历史欢迎文本 |
| `GET /health` | 配置、索引和延迟初始化状态 |
| `GET /logo.png` | 插件图标 |
| `GET /.well-known/ai-plugin.json` | 动态主机插件清单 |
| `GET /.well-known/openapi.yaml` | OpenAPI 3.0.3 |
| `GET /.well-known/example.yaml` | 插件调用示例 |

## 错误

```json
{
  "error": "错误说明",
  "code": "bad_request"
}
```

| HTTP | `code` | 场景 |
|---:|---|---|
| 400 | `bad_request` | JSON、URL、文档或输入不合法 |
| 503 | `service_unavailable` | 凭据、模型依赖、索引或千帆服务不可用 |
| 500 | `internal_error` | 未预期的服务器异常；响应不暴露内部细节 |

当前应用本身不提供身份认证。不要把它直接暴露到公网。
