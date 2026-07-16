# 历史项目审计摘要

## 目录规模

原始目录约有 2265 个文件，混合了：

- 4 套应用 / 开发快照
- 两个失效虚拟环境
- 1.57 GB 重复应用压缩包
- 模型 pickle、Annoy 索引和中间 pickle
- PDF、CAJ、教材、论文与合并文件
- IDE 配置、缓存和实验脚本

权威应用目录约 1.75 GB，其中模型 pickle 约 1.12 GB。

## 关键资产

| 资产 | 大小 | SHA-256 |
|---|---:|---|
| `embedding.pkl` | 1,121,370,859 | `EC0DA9C7316E228838A4EA2B3AC88041A727B299385D64FA322D68FDB2502E39` |
| `2018/index.annoy` | 645,392 | `F28E7B66ECBB147D2756F6AC9E794B8A15BAC677124AC8CFF940D1F1F4C9DE66` |
| `2018/index.pkl` | 25,461 | `08BFBAFA2AEE8E26850CDB2AC5A5EC8AE09DB6CF2D3AB4F61A6DB0B20E057916` |

安全迁移后的 `documents.json` 包含 9 个文档块，维度 768，metric 为 `dot`。

## 历史依赖基线

IDE 实际使用 Python 3.11.4，关键版本为：

- Flask 3.0.3
- Flask-Cors 4.0.0
- LangChain 0.2.5
- LangChain Community 0.2.5
- LangChain Core 0.2.7
- langchain-wenxin 0.10.2
- pydantic 1.10.14
- Annoy 1.17.3
- sentence-transformers 2.4.0
- transformers 4.38.1
- numpy 1.26.4

这些版本仅用于复现历史基线，没有继续作为当前依赖。当前实现已移除旧
LangChain、`langchain-wenxin`、Pydantic 和 NLTK 依赖，并通过
`pip-audit` 检查新的依赖树。

## 不进入公共仓库

- `.venv/`、`venv/`、`.idea/`、`__pycache__/`
- API 凭据和 `.env`
- `embedding.pkl`、`index.pkl` 及其他 pickle
- 原始 CAJ、合并 PDF、压缩包和临时上传配置
- 来源或授权不明确的教材、论文和 Z-Library 文件
- 可重新生成的 `2024617/`、`2024722/`、`merged_with_trans/` 索引

## 原型文档

- [产品使用手册](reference/产品使用手册.docx)
- [项目详细方案](reference/项目详细方案.docx)
- [产品交互演示](media/产品交互演示.mp4)
- [项目演示视频](media/项目演示视频.mp4)
