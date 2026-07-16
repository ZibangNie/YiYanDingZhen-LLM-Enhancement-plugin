# 验证快照

日期：2026-07-16
环境：Windows、Python 3.11.4

## 已通过

| 检查 | 结果 |
|---|---|
| `pytest --disable-socket` | 67 passed |
| 测试覆盖率 | 79.24% |
| `ruff check .` | 通过 |
| `ruff format --check .` | 通过 |
| `mypy src/yiyan_dingzhen` | 通过 |
| `python -m compileall` | 通过 |
| `python -m pip check` | 无依赖冲突 |
| `pip-audit` 全部运行可选依赖 | 无已知漏洞 |
| `bandit -q -r src scripts` | 通过 |
| `python -m build` | sdist 与 wheel 构建成功、无弃用警告 |
| sdist / wheel 内容 | 包含文档、脚本和包内 WSGI；不含索引、pickle、DOCX 或 MP4 |
| wheel 独立安装 | 控制台版本、工作目录解析、包资源和 WSGI 冒烟通过 |
| 插件 JSON / OpenAPI / YAML | 可解析、契约测试通过 |
| `2018/index.annoy` | 大小与 SHA-256 匹配清单；实际加载 9 条映射并返回 3 个结果 |
| `2018/documents.json` | 大小与 SHA-256 匹配清单 |
| 历史主要提示词 | SHA-256 快照一致 |
| 远端 DOCX / MP4 移动 | Git blob 哈希不变 |

依赖审计是在干净虚拟环境中安装以下组合后执行：

```powershell
python -m pip install -e ".[rag,server,tools,security]"
python -m pip_audit --skip-editable
```

## 尚未完成

| 检查 | 原因 |
|---|---|
| 真实千帆问答与文档总结 | 需要仓库所有者轮换后的 API Key，且会产生外部调用或费用 |
| 实际 MPNet 权重 + 旧 Annoy 查询 | 当前机器通过本地代理下载 Hugging Face 大权重文件时无进度；已终止并清理缓存 |
| 本地 Python 3.10 执行 | 当前机器未安装 3.10；GitHub Actions 已配置 3.10 / 3.11 矩阵 |
| 公网插件注册与部署 | 尚未提供正式域名、认证网关或部署环境 |

因此，当前结论是：仓库结构、离线行为、接口契约、依赖和构建已经验证；需要外部账号、网络或部署状态的能力仍应单独验收。
