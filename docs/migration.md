# 从历史原型迁移

## 权威来源

本次整理使用：

```text
D:\code\python\一言鼎臻\一言鼎臻应用
```

作为应用行为基线。依据：

- GitHub 本地旧工作区的 19 个文件与该目录对应文件 SHA-256 完全一致。
- 其他“开发”目录是更早快照。
- 历史 `run.py` 实际加载 `2018/` 索引。
- 18 个主要提示字符串与当前模块逐字一致。

## Git 分支

旧本地 `main` 与远端 `main` 分叉；旧本地历史曾提交约 1.76 GB 文件，并保留一个 1.121 GB 普通 Git blob，不能推送。

规范化工作位于：

```text
refactor/standardize-project
```

它直接从最新 `origin/main` 创建，保留远端文档和视频，但不继承旧巨型提交。

## 代码迁移

| 历史文件 | 新位置 |
|---|---|
| `run.py` | 根兼容入口、`cli.py`、`app.py` |
| `chain.py` | `routing.py` |
| `template_and_prompt.py` | `prompts.py` |
| `model.py` | `llm.py` |
| `query.py` | `query.py` |
| `search.py` | `retrieval.py` |
| `memory.py` | `memory.py` |
| `file_read.py` | `documents.py` |
| `md_translator.py` | `markdown.py` |
| 两个建库实验脚本 | `build_index.py`、`textsplit.py` |
| `paper_reader.py` | `summarize_paper.py` |
| `转pdf.py` | `convert_caj.py` |
| 两份 PDF 合并脚本 | `merge_pdfs.py` |
| `paddle111.py` | `examples/plugin_client.py` |
| 空 `data_process.py` | 删除 |

## 模型和依赖迁移

历史 `langchain-wenxin 0.10.2` 已长期停止更新，并把项目锁在旧 LangChain/Pydantic 依赖树。新运行时：

- 直接调用官方千帆 v2 HTTPS `chat/completions`。
- 使用 `QIANFAN_API_KEY` Bearer 鉴权。
- 仍识别 `BAIDU_API_KEY` 和 `WENXIN_APP_KEY` 作为变量名别名。
- 不再使用 `BAIDU_SECRET_KEY`。
- 用内部路由对象替代 LangChain `MultiPromptChain`。
- 直接使用 `sentence-transformers` 生成归一化嵌入。

历史默认模型 `ernie-bot-turbo` 已不适合作为当前默认值。当前默认采用官方仍列出的 `ernie-4.5-turbo-128k`；部署方可通过 `YDZ_CHAT_MODEL` 选择账号可用模型。

## 明确修复

- 移除源码明文百度凭据。
- 拆分 CLI 与 Flask，消除导入时无限循环。
- 修复 `/set_Query` 未定义上传文件。
- 修复 `/set_text` 下载后弹出本地文件选择框。
- 删除固定 `file.pdf` 并发竞争。
- 延迟初始化模型与索引，路径不再依赖当前目录。
- 将全局跨用户记忆改为有上限的会话隔离。
- 增加 SSRF、超时、重定向、下载和解压限制。
- 修复 Markdown 未闭合代码块。
- 合并重复工具并移除硬编码绝对路径。
- 修复插件动态主机、重复 YAML 键和 OpenAPI 契约。
- 接入历史文档要求但原代码未完成的关键词补位。
- 运行时移除 pickle 和已知高风险旧依赖链。

## 本地资产迁移

从权威目录复制受信历史索引到 Git 忽略目录：

```powershell
Copy-Item `
  "D:\code\python\一言鼎臻\一言鼎臻应用\2018\index.annoy" `
  "artifacts\indexes\2018\index.annoy"

Copy-Item `
  "D:\code\python\一言鼎臻\一言鼎臻应用\2018\index.pkl" `
  "artifacts\indexes\2018\index.pkl"
```

只对可信文件执行：

```powershell
python scripts/migrate_legacy_index.py `
  --legacy-index artifacts\indexes\2018\index.pkl `
  --output artifacts\indexes\2018\documents.json `
  --i-understand-pickle-is-unsafe
```

校验值记录在 `artifacts/manifest.json`。

## 仓库所有者仍需完成

1. 在百度控制台吊销或轮换历史两组凭据，并生成千帆 v2 API Key。
2. 决定正式代码许可证。
3. 确认哪些竞赛资料和索引允许公开再分发。
4. 决定是否把 MP4 移到 GitHub Release 或对象存储。
5. 使用新凭据执行一次会产生费用的问答和文档总结验收。
6. 通过 PR 合并规范化分支；不要推送旧本地 `main` 的巨型历史。
