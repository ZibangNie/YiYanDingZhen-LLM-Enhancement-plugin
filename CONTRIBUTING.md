# 贡献指南

## 本地检查

```powershell
python -m pip install -e ".[dev,security]"
ruff check .
ruff format --check .
mypy src/yiyan_dingzhen
pytest
python -m build
python -m pip_audit --skip-editable
bandit -q -r src scripts
```

默认测试通过 `pytest-socket` 禁止网络，不能下载模型、访问用户文件或调用付费 API。需要外部服务的测试必须标记为 `network` 或 `paid`，并在人工明确启用网络后单独执行。

## 代码约定

- 新代码放在 `src/yiyan_dingzhen/`。
- 一次性离线任务放在 `scripts/`。
- 不要在导入模块时启动服务、弹出 GUI、下载模型或读取大型文件。
- 路径必须基于显式配置或项目资源解析，不能依赖当前工作目录。
- 不要提交真实密钥、模型权重、原始语料、pickle、缓存或生成索引。
- 改动提示词时应补充快照或行为测试。
- 真实模型测试必须使用 `network` 或 `paid` 标记，且不得在普通 PR CI 中启用。

## 提交范围

保持提交单一、可回滚。代码、数据资产和产品文档应分开提交，便于审查版权、体积与运行影响。
