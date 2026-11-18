# 本机 Codex 查询服务器知识库

Windows 11 Pro 上运行 Codex CLI、通过 SSH 连接本服务器，请直接使用 [Windows 安装与验收说明](codex-windows-ssh.md)。已提供 PowerShell 安装脚本和实际服务器地址的配置模板。

当前第一步是在这台服务器上运行 Codex CLI，链路为：Codex CLI → 本机 stdio → `scripts/mcp_stdio.sh` → `app.mcp_server` → `127.0.0.1:8016` HTTP API → SQLite。即使你通过 SSH 登录后运行 Codex，Codex 和知识库进程仍在同一台机器，此时无需再次 SSH。

服务端项目在 `/home/liaozhic/data/mcp`。本方案使用已有的 FastMCP 0.4.1 stdio 支持，不需要升级依赖。

## 当前使用：在这台机器上运行 Codex CLI

将 `configs/codex-mcp-local.toml` 合并到本用户的 `~/.codex/config.toml`，同名的 `knowledge-base` 段只保留一个：

```toml
[mcp_servers.knowledge-base]
command = "bash"
args = ["/home/liaozhic/data/mcp/scripts/mcp_stdio.sh"]
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled_tools = ["list_documents", "search_documents", "get_document"]

[mcp_servers.knowledge-base.tools.list_documents]
approval_mode = "approve"

[mcp_servers.knowledge-base.tools.search_documents]
approval_mode = "approve"

[mcp_servers.knowledge-base.tools.get_document]
approval_mode = "approve"
```

这三个工具仅查询资料，配置为自动允许调用。否则非交互 `codex exec` 可能报 `MCP tool call requires approval, but approval policy is never`。重建索引工具没有启用。

检查注册内容，然后打开新的 Codex 会话：

```bash
codex mcp get knowledge-base
cd /home/liaozhic/data/mcp
codex
```

进入 Codex 后可输入 `/mcp` 查看状态，再问：

> 请使用 knowledge-base 的 list_documents 列出资料，再用 search_documents 搜索 P5-35。请基于返回片段回答，并引用文档标题、document_id 和 chunk_id。

MCP 由 Codex 自动启动和关闭，API 需保持运行。API 和协议自检见下一节。当前用户全局配置生效后，从其他目录启动 Codex 也能使用这个知识库。

2026-11-18 已在本机通过真实 `codex exec` 验收：`knowledge-base.list_documents` 返回 1 份手册；`knowledge-base.search_documents` 使用 `query="P5-35"`、`limit=2` 返回 `document_id=1` 下的 `chunk_id=149` 和 `152`。Codex 完成回答并以退出码 0 结束。

后面的 SSH 配置只用于将来从另一台电脑运行 Codex 访问这台服务器，不需要在当前机器上配置 `knowledge-server` SSH 别名。

## 1. 服务端检查

项目 `.env` 中已统一端口：

```dotenv
APP_HOST=127.0.0.1
APP_PORT=8016
RAW_DIR=raw
DB_PATH=knowledge.db
```

在服务器项目目录执行：

```bash
bash scripts/start_api.sh
```

脚本使用项目虚拟环境，并从 `.env` 读取监听地址。若已有 8016 服务在运行，可继续使用；更新代码后先在其终端按 Ctrl+C，再用上述脚本重启。生产环境可由已有的 systemd 服务管理这个启动脚本。

另开服务器终端做实际 MCP 协议自检：

```bash
cd /home/liaozhic/data/mcp
.venv/bin/python scripts/check_mcp.py --query P5-35
```

自检会启动 stdio 子进程，完成 MCP 初始化、发现工具、列出文档和查询，成功返回退出码 0；连接/鉴权/协议失败会返回非零。查询无匹配会提示但不会视为连接失败。自检不重建索引。

## 2. 后续从另一台电脑连接：准备 SSH

在运行 Codex 的本机配置 SSH 别名 `knowledge-server`。将以下内容合并到本机 `~/.ssh/config`（Windows 原生 OpenSSH 通常是 `%USERPROFILE%\.ssh\config`），将地址、端口和私钥路径换成平时登录服务器使用的值：

```sshconfig
Host knowledge-server
    HostName YOUR_SERVER_ADDRESS
    User liaozhic
    Port 22
    IdentityFile ~/.ssh/id_ed25519
```

也可以直接使用已有 SSH 别名，并相应修改下一步的 Codex 配置。

先从本机正常登录一次，核对并接受服务器主机指纹，确保密钥已授权；有口令的私钥需要先加载到 SSH agent。然后检查非交互登录：

```bash
ssh -T -o BatchMode=yes knowledge-server true
```

该命令应正常退出，不能要求输入密码或输出欢迎语。`BatchMode=yes` 不会配置免密登录，只会在尚未配置好时直接失败。若失败，先完成现有 SSH 密钥登录配置。

## 3. 本机 Codex 配置

将仓库 `configs/codex-mcp.toml` 中的 `[mcp_servers.knowledge-base]` 段合并到**本机** `~/.codex/config.toml`；Windows 原生环境通常对应 `%USERPROFILE%\.codex\config.toml`。保留已有配置，不要重复创建同名段。若设置了自定义 `CODEX_HOME`，使用该目录下的 `config.toml`。

配置仅启用 `list_documents`、`search_documents`、`get_document` 三个查询工具。服务器仍保留 `reindex_documents`，日常查询配置不启用它。

如果使用 Codex CLI，也可以先用下面的一行命令注册，再在生成的配置中补上模板中的超时、`enabled_tools` 和三个查询工具的 `approval_mode`：

```bash
codex mcp add knowledge-base -- ssh -T -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 knowledge-server "bash /home/liaozhic/data/mcp/scripts/mcp_stdio.sh"
```

API_TOKEN 由服务器端 MCP 从项目 `.env` 读取，本机 Codex 配置无需包含 API Token。API 端口继续监听服务器回环地址。

## 4. 从本机验收

先验证本机 SSH 到服务器完整的查询链路：

```bash
ssh -T -o BatchMode=yes knowledge-server "cd /home/liaozhic/data/mcp && .venv/bin/python scripts/check_mcp.py --query P5-35"
```

这一步验证 SSH 登录和服务器端 MCP→API→索引链路。Codex 自身的工具发现和调用还需要继续下面的步骤。

重启本机 Codex 或新开会话；CLI 可执行 `codex mcp get knowledge-base` 检查注册内容，并在交互会话中用 `/mcp` 查看连接状态。配置命令显示成功只代表注册完成，真实工具调用成功才代表全部连通。

在本机 Codex 中输入：

> 请调用 knowledge-base 的 list_documents 列出资料，再用 search_documents 搜索 P5-35。请基于返回片段解释参数含义，并引用文档标题、document_id 和 chunk_id。若片段不足，请调整关键词继续检索，不要猜测。

预期能够看到伺服驱动器手册及命中片段。优先用 `search_documents` 获取少量相关文本；`get_document` 会返回全文，大文档可能超过客户端输出限制。

## 故障排查

- `Cannot reach knowledge API`：检查 API 是否运行、`.env` 的 APP_PORT 是否与监听端口一致。修改 `.env` 后重启 API 和 Codex MCP 会话。
- `authentication failed`：API 和 MCP 必须使用相同的服务端 API_TOKEN。检查是否有旧进程或系统环境变量覆盖了 `.env`。
- `Permission denied (publickey)` / `Host key verification failed`：先修复本机非交互 SSH 登录。
- MCP 初始化失败但 SSH 成功：运行上面的协议自检，检查服务器项目路径和虚拟环境依赖。服务器非交互 shell 和 MCP 脚本的 stdout 必须只有 MCP JSON-RPC；额外日志请写 stderr。
- MCP 已连接但无结果：确认文档已运行 ingest，查询参数编号等简短关键词。当前搜索是 SQLite 全文检索，不是语义搜索。
- 不要将 `/api/search` URL 填入 Codex 的 MCP `url` 字段，它是普通 HTTP API；本方案通过 SSH 启动 stdio MCP。

配置字段依据 OpenAI 官方文档：<https://developers.openai.com/codex/mcp/>。
