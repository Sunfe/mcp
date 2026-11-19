# MCP 文档知识库

将 TXT、PDF、DOCX、DOC 文档解析到 SQLite FTS5，通过 FastAPI 和 MCP stdio 提供文档列表、全文检索及文档读取。支持 Linux 本机 Codex，以及 Windows Codex CLI / App 通过 SSH 访问 Linux 知识库。

完整的部署、SSH 密钥配置、Codex 接入、备份迁移与故障排查见 **[MCP部署与Codex接入手册](MCP部署与Codex接入手册.md)**。

## 快速启动

在 Linux 项目根目录执行，使用 Python 3.10+；读取旧版 `.doc` 还需要系统安装 `antiword`：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

没有 `.env` 时，从示例创建配置：

```bash
cp -n .env.example .env
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

将生成的随机值填入 `.env` 的 `API_TOKEN`。将文档放进 `raw/`，然后执行：

```bash
bash scripts/reindex.sh
bash scripts/start_api.sh
```

API 默认监听 `127.0.0.1:8016`。另开终端做 MCP 协议自检：

```bash
.venv/bin/python scripts/check_mcp.py --query 资料中存在的关键词
```

## Codex 接入

将适合当前机器的模板合并到该机器的 Codex `config.toml`，调整实际路径、SSH 地址和密钥配置：

- [Linux 本机配置](configs/codex-mcp-local.toml)
- [使用 SSH 别名的配置](configs/codex-mcp.toml)
- [Windows SSH 配置](configs/codex-mcp-windows.toml)

本机和 SSH 模板中的服务器目录是已验证环境的示例，迁移时需要修改。API 持续运行，MCP stdio 进程由 Codex 自动启动。

## 开发验证

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 仓库内容与本地数据

仓库保留应用代码、测试、脚本、配置模板和使用文档。真实 `.env`、SSH 私钥、虚拟环境、SQLite 数据库、`raw/` 原始资料、日志和备份均作为本地数据排除；空目录通过 `.gitkeep` 保留。

新机器克隆仓库后，需要自行创建 `.env`、恢复原始文档并建立索引。更新文档后执行 `scripts/reindex.sh`。

历史方案参考保留在 `setup.md` 和 `next.md`；日常部署以本手册和当前代码为准。
