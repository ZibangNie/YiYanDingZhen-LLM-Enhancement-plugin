# 配置

应用启动时从项目根目录 `.env` 和进程环境变量读取配置；进程环境变量优先。

## 模型与检索

| 变量 | 默认值 | 说明 |
|---|---|---|
| `YDZ_PROJECT_ROOT` | 源码根目录或当前工作目录 | `.env` 与默认 `artifacts/` 的基准目录 |
| `QIANFAN_API_KEY` | 无 | 千帆 v2 Bearer API Key，运行必需 |
| `BAIDU_API_KEY` | 无 | 旧变量名兼容别名 |
| `WENXIN_APP_KEY` | 无 | 更早变量名兼容别名 |
| `YDZ_CHAT_MODEL` | `ernie-4.5-turbo-128k` | 千帆模型 ID |
| `YDZ_TEMPERATURE` | `0.9` | 历史生成温度 |
| `YDZ_LLM_TIMEOUT_SECONDS` | `60` | 千帆读取超时 |
| `YDZ_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 维多语言嵌入模型 |
| `YDZ_INDEX_DIR` | `artifacts/indexes/2018` | Annoy 与 JSON 映射目录 |
| `YDZ_RETRIEVAL_K` | `3` | 原文和译文各自的向量候选数；最终知识槽固定为 3 |
| `YDZ_RETRIEVAL_MIN_SCORE` | `0.6` | 历史默认 `dot` 分数阈值 |

旧版 `BAIDU_SECRET_KEY` / `WENXIN_APP_SECRET` 不再使用。若账号中仍有历史 AK/SK，应吊销或轮换，而不是迁移进新配置。

源码可编辑安装会自动识别含 `pyproject.toml` 的仓库根目录。普通 wheel 安装无法依赖源码位置，因此默认使用进程当前工作目录，也可显式设置 `YDZ_PROJECT_ROOT`。

## HTTP 服务

| 变量 | 默认值 | 说明 |
|---|---|---|
| `YDZ_HOST` | `127.0.0.1` | 开发服务监听地址 |
| `YDZ_PORT` | `8081` | 开发服务端口 |
| `YDZ_DEBUG` | `false` | Flask 调试模式；生产环境必须关闭 |
| `YDZ_PUBLIC_BASE_URL` | 请求地址 | 生成插件清单时使用的公网根地址 |
| `YDZ_CORS_ORIGINS` | `https://yiyan.baidu.com` | 逗号分隔的允许来源 |
| `YDZ_MAX_QUERY_CHARS` | `10000` | 问题最大字符数 |
| `YDZ_LOG_LEVEL` | `INFO` | Python 日志级别 |

## 远程文档

| 变量 | 默认值 | 说明 |
|---|---|---|
| `YDZ_DOWNLOAD_TIMEOUT_SECONDS` | `15` | 单次连接和读取超时 |
| `YDZ_DOWNLOAD_MAX_BYTES` | `20971520` | 最大下载字节数 |
| `YDZ_DOWNLOAD_MAX_REDIRECTS` | `3` | 最大重定向次数 |
| `YDZ_ALLOW_HTTP_DOWNLOADS` | `false` | 是否允许明文 HTTP |
| `YDZ_ALLOWED_DOWNLOAD_HOSTS` | 空 | 可选逗号分隔域名白名单 |

公开部署建议设置严格的 `YDZ_ALLOWED_DOWNLOAD_HOSTS`。子域名会匹配白名单父域名。

## 会话记忆

| 变量 | 默认值 | 说明 |
|---|---|---|
| `YDZ_MEMORY_TURNS` | `10` | 单个会话最多保留轮次 |
| `YDZ_MEMORY_SESSIONS` | `512` | 进程内最多保留会话数 |

记忆只存在于当前进程内，不会持久化；多进程部署的会话状态不会自动共享。
