# 一言鼎臻

一言鼎臻是一个面向 PT、CYPT、CUPT、IYPT 等物理竞赛场景的知识库增强问答与文档总结项目。当前版本把历史实验原型整理为标准 Python 包，同时保留两个插件接口、双语检索、两级提示路由、13 个物理子领域、本地 Annoy 知识库和短期会话记忆。

本仓库能够证明的是本地代码、接口清单和测试已具备；2024 年资料中的文心插件页面属于历史演示，不代表当前已有公网部署。

## 核心能力

- 中英文语种判断、关键词提取、翻译与双路向量检索
- 检索低于阈值时使用关键词结果补位
- “物理 / 总结 / 生活”一级路由和 13 个物理子路由
- 每次回答最多组合 3 个知识库片段和 3 个同会话历史片段
- PDF、DOCX、Markdown、TXT 文档读取与分层总结
- `POST /set_Query`、`POST /set_text` 及百度插件清单兼容接口
- CLI、Flask 开发服务和 Waitress WSGI 部署入口
- 安全索引迁移、索引重建、CAJ 转换、PDF 合并等离线工具

## 环境要求

- Python 3.10 或 3.11
- 百度千帆 v2 Bearer API Key
- 本地 `index.annoy` 和 `documents.json`
- 首次运行需要下载约 1 GB 的多语言 MPNet 嵌入模型

项目使用千帆 v2 的 OpenAI 兼容 `chat/completions` 接口；旧版 AK/SK 适配库不再是运行依赖。千帆当前的鉴权和接口示例见[百度智能云官方文档](https://cloud.baidu.com/doc/qianfan-docs/s/Imkdq47r5)。

## 快速开始

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[rag,server]"
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
QIANFAN_API_KEY=重新生成的千帆_v2_API_Key
YDZ_CHAT_MODEL=ernie-4.5-turbo-128k
YDZ_INDEX_DIR=artifacts/indexes/2018
```

历史源码中的两组凭据已经暴露，必须在百度控制台吊销或轮换，不能复制到 `.env`。

## 准备本地索引

默认目录：

```text
artifacts/indexes/2018/
├─ index.annoy
└─ documents.json
```

本地工作区已经从可信历史 `index.pkl` 迁移出 JSON 映射；这些生成资产被 Git 忽略。其他环境可按 [artifacts/README.md](artifacts/README.md) 和 [docs/migration.md](docs/migration.md) 迁移。

仅对项目所有者确认可信的旧文件执行：

```powershell
python scripts/migrate_legacy_index.py `
  --legacy-index artifacts/indexes/2018/index.pkl `
  --output artifacts/indexes/2018/documents.json `
  --i-understand-pickle-is-unsafe
```

从自有文档重建索引：

```powershell
python scripts/build_index.py .\data\my-physics-corpus `
  --output artifacts/indexes/custom
```

随后把 `.env` 中的 `YDZ_INDEX_DIR` 改为 `artifacts/indexes/custom`。

## 运行

交互问答：

```powershell
python run.py
```

单次问答或本地文档总结：

```powershell
python -m yiyan_dingzhen ask "什么是单镜望远镜的主要像差？"
python -m yiyan_dingzhen summarize .\paper.pdf
```

启动开发服务：

```powershell
python run.py serve --host 127.0.0.1 --port 8081
```

生产环境可使用：

```powershell
waitress-serve --call yiyan_dingzhen.wsgi:create_application
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8081/health
```

问答调用：

```powershell
$body = @{
  query_content = "请分析 IYPT 单镜望远镜问题"
  session_id = "demo-user"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8081/set_Query `
  -ContentType application/json `
  -Body $body
```

完整接口契约见 [docs/api.md](docs/api.md)，全部配置见 [docs/configuration.md](docs/configuration.md)。

## 开发与验证

```powershell
python -m pip install -e ".[dev,security]"
ruff check .
ruff format --check .
mypy src/yiyan_dingzhen
pytest
python -m build
python -m pip_audit --skip-editable
```

默认测试不会访问网络、下载模型或调用付费 API。真实千帆问答与文档总结需要仓库所有者使用已轮换凭据单独验收。

## 项目结构

```text
src/yiyan_dingzhen/   核心包、插件清单和资源
scripts/              索引及文档离线工具
examples/             HTTP 调用示例
tests/                单元、契约和集成测试
artifacts/            本地资产规范与校验清单
docs/                 架构、接口、配置、迁移与历史资料
.github/              CI、Dependabot 和协作模板
```

## 安全与许可

- 远程文档下载默认只接受公网 HTTPS，并限制 DNS、重定向、超时和大小。
- 运行时不加载 pickle；迁移脚本也只能处理可信本地历史文件。
- 模型权重、原始论文、教材、CAJ、pickle 和生成索引不进入普通 Git。
- 公网部署必须在 API Gateway 或反向代理层增加认证、限流和 TLS。
- 当前仓库尚未授予开源许可证，详见 [LICENSE](LICENSE)。

更多信息：

- [架构](docs/architecture.md)
- [产品行为基线](docs/product-baseline.md)
- [历史迁移](docs/migration.md)
- [历史审计](docs/legacy-audit.md)
- [验证快照](docs/validation.md)
- [安全说明](SECURITY.md)
- [贡献指南](CONTRIBUTING.md)
