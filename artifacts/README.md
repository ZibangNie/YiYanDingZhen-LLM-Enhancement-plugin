# 本地模型与索引

此目录只跟踪说明和校验清单，不跟踪模型权重、pickle、原始语料或生成索引。

默认运行目录：

```text
artifacts/indexes/2018/
├─ index.annoy
└─ documents.json
```

历史原型还需要 `embedding.pkl` 和 `index.pkl`。新实现不在运行时加载它们：

- 嵌入模型由 `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` 正常初始化。
- `index.pkl` 通过一次性迁移脚本转成 JSON。

迁移历史索引：

```powershell
python scripts/migrate_legacy_index.py `
  --legacy-index artifacts/indexes/2018/index.pkl `
  --output artifacts/indexes/2018/documents.json `
  --i-understand-pickle-is-unsafe
```

然后按 `manifest.json` 校验 SHA-256。原始 PDF、CAJ、教材和论文是否可以再分发需要单独确认，不应直接加入公共仓库。

PowerShell 校验示例：

```powershell
Get-FileHash artifacts\indexes\2018\index.annoy -Algorithm SHA256
Get-FileHash artifacts\indexes\2018\documents.json -Algorithm SHA256
```

两个结果必须分别与 `manifest.json` 中的记录一致。嵌入模型名称、维度、metric 和归一化设置也记录在清单的 `runtime` 节点中；重建索引时不能只替换模型而继续复用旧索引。
