# MCP 知识库部署、Codex 接入与迁移手册

整理日期：2026-11-18。适用于本项目当前代码。

Linux 本机 Codex CLI 和 Windows 11 Pro 上的 Codex CLI 通过 SSH 查询知识库，两种方式均已跑通。Linux 端经过实际工具调用验证；Windows 端由使用者确认成功。以后更换服务器或 Windows 电脑，按本手册重新配置即可。

## 快速选择

| 当前需求 | 从哪里开始 |
|---|---|
| 新服务器从零部署 | 第 2 节：部署 Linux 服务端 |
| 在服务器本机运行 Codex | 第 4 节：Linux 本机 Codex 配置 |
| 新 Windows 电脑连接现有服务器 | 第 5 节：Windows 准备；再完成第 6 节配置 |
| 使用 Codex 桌面 App 图形界面 | 第 6.5 节：复用 CLI 配置或从界面添加 |
| SSH 目前只能输入密码 | 第 5.2 节：生成密钥；第 5.3 节：上传公钥 |
| 更换服务器或项目目录 | 第 8 节：迁移清单 |
| 添加或更新文档 | 第 7 节：日常操作 |
| 连接失败、工具报错或没有结果 | 第 9 节：分层排查 |

## 1. 架构、参数与文件位置

### 1.1 两种已验证的连接方式

Linux 本机使用：

```text
Linux 上的 Codex CLI
  → bash scripts/mcp_stdio.sh
  → MCP stdio 进程
  → http://127.0.0.1:8016 的 HTTP API
  → SQLite 文档索引
```

Windows 远程使用：

```text
Windows 上的 Codex CLI
  → Windows ssh.exe
  → Linux 上的 bash scripts/mcp_stdio.sh
  → MCP stdio 进程
  → Linux 的 http://127.0.0.1:8016
  → SQLite 文档索引
```

API 需要持续运行；MCP stdio 进程由每个 Codex 会话自动启动和关闭。Windows 只需要 Codex CLI 和 OpenSSH 客户端，Python、文档、SQLite 和 API Token 都在 Linux 上。

如果先 SSH 登录 Linux 再执行 `codex`，使用的是 Linux 本机方式。要使用 Windows 远程方式，应在 Windows PowerShell 中直接执行 `codex`。

### 1.2 更换机器前先记录这些参数

| 参数 | 当前已使用的值 | 换机器时需要做什么 |
|---|---|---|
| 服务器地址 | `66.245.192.250` | 改为新服务器 IP 或域名 |
| SSH 用户 | `liaozhic` | 改为新服务器上的实际用户 |
| SSH 端口 | `22` | 自定义端口时一起修改 SSH 和 SCP 命令 |
| Linux 项目目录 | `/home/liaozhic/data/mcp` | 修改 Codex 远程命令、systemd 路径 |
| API 地址 | `127.0.0.1:8016` | `.env` 中的端口与 API 实际监听端口必须一致 |
| 原始文档目录 | 项目内 `raw/` | `.env` 中 `RAW_DIR=raw` |
| 数据库位置 | 项目内 `knowledge.db` | `.env` 中 `DB_PATH=knowledge.db` |
| Codex MCP 名称 | `knowledge-base` | 可沿用；配置表不能重名 |
| Windows 密钥名 | 示例：`codex_knowledge_ed25519` | 使用你实际生成的密钥；本文不假定每台电脑名称相同 |

本手册命令以当前地址、用户和目录为例。新服务器需要替换对应内容；TOML、SSH config、systemd 配置中的路径是实际字面值，不会自动替换成前文变量。

### 1.3 配置文件分别属于哪台机器

| 文件 | 所在机器 | 用途 |
|---|---|---|
| 项目根目录 `.env` | Linux | API 地址、Token、文档和数据库位置 |
| `~/.codex/config.toml` | Linux | 在 Linux 运行 Codex 时使用 |
| `%USERPROFILE%\.codex\config.toml` | Windows | 在 Windows 运行 Codex 时使用 |
| `%USERPROFILE%\.ssh\config` | Windows | SSH 地址、用户、端口和私钥别名 |
| `~/.ssh/authorized_keys` | Linux 登录用户目录 | 允许哪些客户端公钥登录 |

若设置了自定义 `CODEX_HOME`，Codex 使用该目录中的 `config.toml`。不要用新配置覆盖整个现有文件；合并或替换同名 MCP 配置段，保留模型、登录和其他服务设置。

## 2. 部署 Linux 服务端

以下命令在 **Linux Bash** 执行。

### 2.1 放好项目并安装依赖

将本项目当前已修复的代码、`scripts/`、`configs/` 和原始文档复制到新服务器。不要只依赖旧 `setup.md` / `next.md` 中的代码片段，它们保留了部分历史示例。

Ubuntu / Debian 的基础依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip antiword openssh-server
python3 --version
```

项目要求 Python 3.10+，现有环境使用 Python 3.11。迁移时建议使用相同的 Python 大版本和仓库锁定的依赖；不要顺便升级 FastMCP。

```bash
cd /home/liaozhic/data/mcp
mkdir -p raw data logs
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

`.venv` 应在目标机器重新创建，不要跨机器、操作系统或项目路径直接复制旧虚拟环境。

当前锁定 `fastmcp==0.4.1`、`mcp==1.1.2`；该组合使用 stdio。历史文档里的 `streamable-http` 示例不适用于当前版本。

### 2.2 创建或检查 `.env`

```bash
nano .env
```

新建时可使用以下内容；已有文件则修改需要调整的项：

```dotenv
APP_NAME=MCP Knowledge Server
APP_HOST=127.0.0.1
APP_PORT=8016
API_TOKEN=REPLACE_WITH_A_RANDOM_TOKEN
RAW_DIR=raw
DB_PATH=knowledge.db
LOG_LEVEL=info
DEFAULT_SEARCH_LIMIT=5
MAX_SEARCH_LIMIT=20
CHUNK_SIZE=800
CHUNK_OVERLAP=100
```

在服务器生成随机 Token，将结果填入 `API_TOKEN`：

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'
chmod 600 .env
```

Token 只保存在服务器。API 和 MCP 都读取这份配置，Windows 无需填写 API Token。

`RAW_DIR`、`DB_PATH` 的相对路径以项目根目录为基准。数据库父目录必须已存在。系统环境变量优先于 `.env`；修改配置后，重启 API，并新开 Codex 会话以重启 MCP。

### 2.3 放入文档并建立索引

将 `.txt`、`.pdf`、`.docx`、`.doc` 放入 `raw/`，可以按子目录分类，例如 `raw/product/`。

```bash
cd /home/liaozhic/data/mcp
bash scripts/reindex.sh
```

等价命令：

```bash
source .venv/bin/activate
python -m app.ingest
```

首次执行会显示 `[PARSING]`、`[INGESTED]` 和 `[DONE]`。重复执行，未修改的文档显示 `[UNCHANGED]`。解析结果写入 SQLite，不会在 `raw/` 生成文本文件。

已验证的参考结果：一份 DS5L1 伺服驱动器手册，324 个文本块。新资料库的数量可以不同。

### 2.4 启动 API 并验证 MCP

先在一个 Linux 终端中运行：

```bash
cd /home/liaozhic/data/mcp
bash scripts/start_api.sh
```

脚本自动使用项目虚拟环境和 `.env` 中的监听地址。保持此终端运行，在另一个 Linux 终端验证：

```bash
curl --fail http://127.0.0.1:8016/health
cd /home/liaozhic/data/mcp
.venv/bin/python scripts/check_mcp.py --query P5-35
```

参考输出：

```text
[OK] MCP initialized: KnowledgeBaseMCP
[OK] Tools: list_documents, search_documents, get_document, reindex_documents
[OK] Indexed documents: 1
[OK] Search 'P5-35': 5 result(s)
```

自检会真实启动 MCP，完成初始化、工具发现、列出文档和检索。若新资料不包含 `P5-35`，换成资料中确定存在的关键词。零结果不一定表示连接失败。

## 3. 让 Linux API 在退出 SSH 后持续运行

长期作为服务器时，建议由 systemd 管理 API。以下是新服务器部署方法，不表示现有机器已经安装了这个服务。

**在 Linux 执行。** 如果当前 API 在前台占用 8016，先在它的终端按 Ctrl+C。若已由其他服务管理，则检查并修改现有服务，避免重复启动。

```bash
sudo nano /etc/systemd/system/mcp-knowledge-api.service
```

写入以下内容；更换用户或项目目录时修改 `User`、`WorkingDirectory`、`ExecStart`：

```ini
[Unit]
Description=MCP Knowledge HTTP API
After=network.target

[Service]
Type=simple
User=liaozhic
WorkingDirectory=/home/liaozhic/data/mcp
ExecStart=/usr/bin/bash /home/liaozhic/data/mcp/scripts/start_api.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-knowledge-api
sudo systemctl status mcp-knowledge-api --no-pager
curl --fail http://127.0.0.1:8016/health
```

维护命令：

```bash
sudo systemctl restart mcp-knowledge-api
sudo journalctl -u mcp-knowledge-api -n 100 --no-pager
```

API 继续绑定服务器回环地址。Windows 连接使用 SSH 端口，无需开放 8016 的公网访问，也无需配置 SSH 端口转发。stdio MCP 本身由 Codex 启动，无需另建常驻服务。

## 4. Linux 本机 Codex 配置

仅在需要从 Linux 本机运行 Codex 时做本节。Windows 远程接入不依赖服务器安装 Codex。

先确认已安装 Codex CLI，并完成登录或已有模型提供方配置：

```bash
codex --version
```

新机器可按官方 Codex CLI 安装说明安装；常见 npm 方式是 `npm install -g @openai/codex`，然后 `codex login`，前提是已安装受支持的 Node.js/npm。

合并以下内容到 Linux 用户的 `~/.codex/config.toml`：

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

模板也位于 [configs/codex-mcp-local.toml](configs/codex-mcp-local.toml)。三个工具只查询文档；`reindex_documents` 不在日常查询允许列表中。

```bash
codex mcp get knowledge-base
codex
```

新会话中输入 `/mcp`，再要求 Codex 使用 `knowledge-base` 搜索 `P5-35`。仅 `codex mcp get` 成功说明配置被读取；实际工具返回文档，才说明整个链路可用。

## 5. Windows 准备 SSH 和 Codex

本节命令在 **Windows PowerShell** 执行。若已经有可用密钥，可跳过生成与上传，直接配置 SSH 别名并验证。

### 5.1 检查客户端

```powershell
ssh -V
codex --version
```

如果没有 `ssh.exe`，在 Windows“可选功能”中安装 **OpenSSH 客户端**。Windows 这边不需要安装 OpenSSH 服务器。

如果没有 Codex CLI，先安装 Node.js LTS，再执行：

```powershell
npm.cmd install -g @openai/codex
codex.cmd login
```

已有登录或模型提供方配置时继续使用原设置。如果 PowerShell 阻止 `codex.ps1`，后面的 `codex` 命令可以使用 `codex.cmd` 替代。

### 5.2 生成专用密钥

密码登录可以用于安装公钥。正式 MCP 连接需要非交互认证；TOML 没有 SSH `password` 字段，`BatchMode=yes` 会在需要密码输入时直接失败。

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
$McpKey = "$env:USERPROFILE\.ssh\codex_knowledge_ed25519"
ssh-keygen -t ed25519 -f $McpKey -C "codex-knowledge"
```

如提示同名文件已存在，选择保留旧文件并复用，或使用新名称，避免覆盖。

密钥口令有两种用法：不设口令时直接使用私钥；设置口令时需先通过 SSH agent 解锁。服务器账号密码和私钥口令是两回事。

若设置了私钥口令，在 **管理员 PowerShell** 中启用 agent：

```powershell
Set-Service -Name ssh-agent -StartupType Automatic
Start-Service ssh-agent
```

然后在平时运行 Codex 的 Windows 用户下加载密钥：

```powershell
ssh-add "$env:USERPROFILE\.ssh\codex_knowledge_ed25519"
ssh-add -l
```

### 5.3 将公钥加入 Linux 登录用户

先填写实际参数，随后两条命令可能要求输入服务器密码：

```powershell
$McpServer = "66.245.192.250"
$McpUser = "liaozhic"
$McpPort = 22
$McpKey = "$env:USERPROFILE\.ssh\codex_knowledge_ed25519"

scp -P $McpPort "$McpKey.pub" "${McpUser}@${McpServer}:codex_knowledge_ed25519.pub"
ssh -p $McpPort "${McpUser}@${McpServer}" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat ~/codex_knowledge_ed25519.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

注意 `scp` 使用大写 `-P` 指定端口，`ssh` 使用小写 `-p`。上传 `.pub` 公钥即可，私钥保留在 Windows。首次连接时，核对服务器主机指纹后确认。

不需要关闭 Linux 的密码登录。只需服务器同时允许该用户进行公钥认证。如果服务器策略禁止公钥认证，需要先由管理员调整。

### 5.4 用固定 SSH 别名简化以后迁移

在 Windows 打开 SSH 配置，保留已有内容：

```powershell
notepad "$env:USERPROFILE\.ssh\config"
```

加入以下段；已有 `knowledge-server` 段就修改它：

```sshconfig
Host knowledge-server
    HostName 66.245.192.250
    User liaozhic
    Port 22
    IdentityFile ~/.ssh/codex_knowledge_ed25519
    IdentitiesOnly yes
```

以后只更换服务器 IP、SSH 端口或 Windows 密钥时，优先修改这个别名，Codex 配置继续使用 `knowledge-server`。

验证非交互登录：

```powershell
ssh -T -o BatchMode=yes knowledge-server "echo SSH_OK"
```

必须直接输出 `SSH_OK`，不能再要求输入服务器密码或私钥口令。

## 6. Windows Codex 通过 SSH 接入

### 6.1 先验证 Windows 到服务器的查询链路

**在 Windows PowerShell 执行：**

```powershell
ssh -T -o BatchMode=yes knowledge-server "/home/liaozhic/data/mcp/.venv/bin/python /home/liaozhic/data/mcp/scripts/check_mcp.py --query P5-35"
```

看到 MCP 初始化、文档列表、查询均成功后，再配置 Codex。这个命令验证的是 SSH 和服务器查询链路；下一步才验证 Windows Codex 的实际调用。

### 6.2 合并完整的 Windows Codex 配置

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex" | Out-Null
notepad "$env:USERPROFILE\.codex\config.toml"
```

若使用自定义 `CODEX_HOME`，编辑那个目录下的配置。保留已有内容，将以下配置合并进去；同名服务表和工具子表只能各有一份：

```toml
[mcp_servers.knowledge-base]
command = "ssh.exe"
args = [
  "-T",
  "-o", "BatchMode=yes",
  "-o", "ConnectTimeout=10",
  "-o", "ServerAliveInterval=30",
  "-o", "ServerAliveCountMax=3",
  "knowledge-server",
  "bash /home/liaozhic/data/mcp/scripts/mcp_stdio.sh"
]
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

`-T` 禁用伪终端，`BatchMode=yes` 使用非交互认证，保活参数帮助检测断开的 SSH 会话。三个查询工具的 `approval_mode` 允许 Codex 实际调用它们，包括非交互 `codex exec`。

如果不使用别名，可以将 `knowledge-server` 换成 `liaozhic@66.245.192.250`，并在该参数之前添加 `"-p", "22"` 和 `"-i", "C:/Users/实际用户名/.ssh/codex_knowledge_ed25519"`。TOML 中 Windows 路径可用正斜杠；不要直接写 `$env:USERPROFILE`，TOML 不会按 PowerShell 规则展开它。

Windows 的 `127.0.0.1` 指向 Windows 本机；本方案无需让 Windows 访问 8016，SSH 启动的 Linux MCP 会访问 Linux 自己的回环地址。

### 6.3 在 Windows 真正调用工具

新开 Windows 终端和 Codex 会话：

```powershell
codex mcp get knowledge-base
codex
```

进入 Codex 后用 `/mcp` 查看服务，再输入：

> 请调用 knowledge-base 的 list_documents 列出资料，再调用 search_documents 搜索 P5-35，limit 为 2。基于返回片段回答，并引用文档标题、document_id 和 chunk_id。没有结果就明确说明。

也可以非交互验证：

```powershell
codex exec --ephemeral --sandbox read-only "请只使用 knowledge-base MCP：先调用 list_documents，再调用 search_documents，query=P5-35，limit=2。报告真实结果和来源编号。不要执行 shell 或修改文件。"
```

不能只看进程退出码；确认输出中两个 MCP 工具均成功，并实际返回资料。本项目此前命中的示例为 `document_id=1`、`chunk_id=149` / `152`；重新导入后这些编号可能变化。

### 6.4 可选：使用已有 PowerShell 安装脚本

手工配置是本手册的基础流程。需要自动检查 SSH、备份并合并配置时，可在 Windows 下载项目中的脚本：

```powershell
scp knowledge-server:/home/liaozhic/data/mcp/scripts/setup_codex_windows.ps1 .\setup_codex_windows.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_codex_windows.ps1 -ServerAddress knowledge-server -UserName liaozhic -Port 22 -RemoteProject /home/liaozhic/data/mcp -Verify
```

更换机器后显式传入新用户、端口、目录；脚本的默认值仍是原服务器参数。它会备份现有配置，只管理自己添加的配置块。已有手工配置的同名服务时，脚本会保存候选配置并提示合并，不会直接覆盖。

### 6.5 Codex 桌面 App 图形界面

官方 MCP 文档说明：桌面 App、Codex CLI 和 IDE 扩展可以共用 Codex 配置。对本项目，Windows App 与已经跑通的 Windows 原生 CLI 使用相同 Windows 用户、相同 `CODEX_HOME` / 默认配置目录，并在 Windows 本地环境执行时，可直接复用第 6.2 节的 SSH 配置。

已经通过 CLI 配置成功时：

1. 确认配置位于该 Windows 用户的 `%USERPROFILE%\.codex\config.toml`，或双方共同使用的自定义 `CODEX_HOME`。
2. 重新启动桌面 App，打开 **Settings / 设置 → MCP servers**，查看 `knowledge-base` 并确认已启用；不要重复添加同名服务。
3. 若界面提供 **Restart / 重启**，按提示重新加载。新建使用 Windows 本地环境的会话，在输入框使用 `/mcp` 查看连接。
4. 输入第 6.3 节的查询提示，确认 App 实际调用工具并返回文档片段。

如果尚未配置 CLI，也可以在 App 的 **Settings → MCP servers → Add server** 中添加。字段参考：

| 界面字段 | 本项目应填写的值 |
|---|---|
| Name / 名称 | `knowledge-base` |
| Transport / 类型 | `STDIO` |
| Command / 命令 | `ssh.exe` |
| Arguments / 参数 | 第 6.2 节 `args` 数组里的各个参数，保持顺序 |
| 环境变量 | 本方案不需要填写 API Token |

若界面没有工具权限和超时字段，仍可编辑 `config.toml`，使用第 6.2 节的完整配置。远程 SSH 命令 `bash /home/liaozhic/data/mcp/scripts/mcp_stdio.sh` 是一个参数；不要因按空格拆分而改变其参数边界。

此处选择 STDIO，是因为 App 启动本地 `ssh.exe` 并通过它的标准输入输出连接 MCP。服务器位于远端，不代表应填写 HTTP URL；`/api/search` 是普通 HTTP API，不是 MCP Endpoint。

CLI 可用但 App 不可用时，依次检查：

- **配置目录和用户**：App 是否与 CLI 使用同一 Windows 用户；CLI 是否只在当前终端设置了自定义 `CODEX_HOME`，而 App 没有继承它。
- **执行环境**：WSL 内的 CLI 使用 Linux 用户目录；Windows 原生 App 不会自动等同于该 WSL 配置。App 若选择了远端或云端执行环境，MCP 配置和 `ssh.exe` 的运行位置也需按那个环境检查。
- **SSH 可执行文件**：在 Windows PowerShell 用 `(Get-Command ssh.exe).Source` 查询实际路径。App 找不到命令时，将 `command` 改成该绝对路径，TOML 中可写成 `C:/Windows/System32/OpenSSH/ssh.exe`（以实际安装位置为准）。
- **密钥解锁**：有口令的私钥要加载到 Windows SSH agent；终端曾经输入过一次服务器密码不等于 App 可以非交互登录。
- **旧会话**：修改配置后重新启动 App 并新建会话；确认 Linux API 仍在运行。

Linux 桌面 App 如使用本机执行环境，则复用第 4 节的 Linux 本机配置。界面菜单可能随版本变化，配置文件与真实工具调用是验证依据。

## 7. 日常操作

### 7.1 上传或修改资料

例如从 Windows 上传一份 PDF：

```powershell
scp "C:\Docs\新手册.pdf" knowledge-server:/home/liaozhic/data/mcp/raw/
ssh knowledge-server "bash /home/liaozhic/data/mcp/scripts/reindex.sh"
```

程序没有自动监听目录，新文件或文件修改后需要重新运行 ingest。删除 `raw/` 中的文件后再次索引，对应旧索引也会删除。

不要把 `RAW_DIR` 临时指向一个错误的、但确实存在的空目录来运行索引：当前增量逻辑会将未扫描到的旧文档视为已删除。不存在的目录会报错并保留旧索引。

### 7.2 常用查询方式

- `list_documents`：了解资料库中有什么。
- `search_documents`：优先查询参数编号、型号或简短关键词。
- `get_document`：根据 `document_id` 取全文，仅在确实需要时使用；大文档可能超过客户端输出限制。

搜索是 SQLite FTS5 全文检索，不是语义检索。多个空白分隔的关键词需要同时命中。`P5-35` 可直接输入，后端已修复特殊符号触发查询语法错误的问题；标点通常作为分词分隔符，所以也可能匹配 `P5 35`。

扫描版 PDF 需要另做 OCR，当前解析器不会自动 OCR。没有提取到文字时会显示 `[SKIP]`。

### 7.3 更新代码或配置后的重启

API 由 systemd 管理时，在 Linux 执行：

```bash
sudo systemctl restart mcp-knowledge-api
```

前台运行则按 Ctrl+C 后重新执行 `bash scripts/start_api.sh`。修改 MCP 代码、`.env` 或 Codex 配置后，在使用端新开 Codex 会话，以加载新的 MCP 进程。

## 8. 迁移和备份

### 8.1 要保存什么

| 内容 | 是否需要迁移 | 说明 |
|---|---|---|
| 最新代码、脚本、配置模板、本手册 | 是 | 包括尚未提交 Git 的修改和新增文件 |
| `raw/` 原始资料 | 是 | 可以重新生成索引的原始来源 |
| `.env` | 保留或重新创建 | 通常被 Git 忽略，`git clone` 不会自动恢复它 |
| SQLite 数据库 | 可备份 | 原始文档齐全时也可重新索引；包含提取出的文档内容 |
| `.venv/` | 不直接迁移 | 在目标路径重新创建并安装依赖 |
| systemd 配置 | 记录后重新安装 | 用户、工作目录和启动路径可能变化 |
| Windows SSH 私钥 | 留在对应客户端 | 新 Windows 电脑可新建密钥并重新授权 |
| Windows Codex 配置 | 合并迁移 | 知识库段可复用，其他设置依机器情况调整 |

当前数据库是项目根目录的 `knowledge.db`，不要误以为一定在 `data/knowledge.db`。以 `.env` 的 `DB_PATH` 为准。

### 8.2 制作可迁移的项目备份

在 Linux 项目根目录执行。期间暂停文档上传和 ingest；如果 API 可触发索引，也先停止它，保持文档与数据库一致。以下目录名已排除在归档之外，可以重复制作备份：

```bash
cd /home/liaozhic/data/mcp
mkdir -p backups
chmod 700 backups
```

使用 SQLite 的备份接口创建数据库快照：

```bash
.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
from app.config import settings

source_path = Path(settings.db_path)
if not source_path.is_file():
    raise SystemExit(f"Database not found: {source_path}")
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
backup_path = Path("backups") / f"knowledge-{stamp}.db"
with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
    with sqlite3.connect(backup_path) as target:
        source.backup(target)
os.chmod(backup_path, 0o600)
print(backup_path)
PY
```

再归档源代码、原始资料和 `.env`，排除虚拟环境与运行中的数据库文件：

```bash
umask 077
MCP_BACKUP_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
tar --exclude='./.venv' --exclude='./.git' --exclude='./.codex' --exclude='./.agents' --exclude='./.aws' --exclude='./logs' --exclude='./backups' --exclude='__pycache__' --exclude='*.db' --exclude='*.db-*' -czf "backups/mcp-project-${MCP_BACKUP_STAMP}.tar.gz" .
```

迁移时带走归档和单独生成的数据库快照。归档包含 `.env`，应按服务器配置备份保存，不要发布为公共下载文件。如果自定义数据库文件名不以 `.db` 结尾，归档时也排除它；数据库内容以 SQLite 快照为准。

### 8.3 更换 Linux 服务器

1. 在新服务器准备登录用户和项目目录，复制或解压最新项目及原始资料。
2. 按第 2 节重建 `.venv`，恢复或创建 `.env`，确认 `RAW_DIR` 和 `DB_PATH`。
3. 可以将数据库快照复制到新的 `DB_PATH`；也可以在没有数据库时直接运行 ingest 重新生成。
4. 在新位置运行 `bash scripts/reindex.sh`。数据库记录了文档绝对路径，迁移路径或文件时间变化后需要重新扫描。原始资料要先复制完整。
5. 按第 3 节配置 API 常驻，再运行 MCP 自检。
6. 将 Windows 公钥安装到新服务器对应用户的 `authorized_keys`。
7. 修改 Windows SSH `knowledge-server` 别名的 `HostName`、`User`、`Port`；项目路径改变时，也修改 Windows Codex 远程命令。
8. 如果 Linux 本机也要用 Codex，更新 Linux 的本机 MCP 路径。
9. Windows 重做 `SSH_OK`、远端自检、Codex 工具调用三步验证，再切换日常使用。

如果新服务器沿用旧 IP 但 SSH 主机密钥发生变化，先通过服务器控制台核对新指纹；确认是预期迁移后，再移除旧记录。例如默认 22 端口使用 `ssh-keygen -R 66.245.192.250`；自定义端口使用 `ssh-keygen -R "[66.245.192.250]:2222"`。随后正常 SSH 连接并确认新指纹，不要通过关闭主机验证来绕过提示。

### 8.4 只更换 Windows 电脑

1. 安装 OpenSSH 客户端和 Codex CLI，恢复自己的 Codex 登录或模型提供方设置。
2. 在新电脑创建 SSH 密钥，将新公钥加入服务器；不需要重新部署 API 或解析文档。
3. 配置 `knowledge-server` 别名，确认密钥路径指向新电脑上的实际文件。
4. 合并第 6.2 节的 Windows MCP 配置。
5. 完成 SSH、远端自检和 Codex 调用验证。

旧电脑停止使用后，可以从服务器 `authorized_keys` 中移除它对应的旧公钥；先确认新电脑已经连接成功。

### 8.5 同时更换服务器和 Windows

先部署新服务器并在 Linux 上通过自检；再在新 Windows 上创建密钥、安装公钥、配置 SSH 和 Codex。不要同时排查两个尚未验证的环节。

## 9. 分层验证与常见故障

按以下顺序定位：

| 层级 | 命令 / 操作 | 能证明什么 |
|---|---|---|
| Linux API | Linux：`curl --fail http://127.0.0.1:8016/health` | HTTP 服务已运行 |
| Linux MCP | Linux：`.venv/bin/python scripts/check_mcp.py --query P5-35` | MCP 初始化、API 鉴权、文档查询可用 |
| Windows SSH | Windows：`ssh -T -o BatchMode=yes knowledge-server "echo SSH_OK"` | Windows 能非交互登录 |
| Windows 到远端查询 | Windows：第 6.1 节命令 | SSH 与服务端查询链路可用 |
| Windows Codex | 新会话 `/mcp`，实际调用搜索工具 | Codex 已加载并成功使用该 MCP |

| 现象 | 常见原因与处理 |
|---|---|
| ingest 没有解析到文档 | 检查 `[START] RAW_DIR`，原问题是 `mcp` 误写成 `mcpp`；确认文件扩展名受支持 |
| `[UNCHANGED]` | 文档未修改，已有索引，属于正常情况 |
| `Cannot reach knowledge API` | 检查 API 是否运行；尤其注意 `.env` 是 8016，但进程可能启动在 8000，或反过来 |
| HTTP 401 / authentication failed | API 与 MCP 的 Token 不一致或旧进程未重启；检查服务器环境变量覆盖 |
| 搜索 `P5-35` 报 `no such column: 35` | 使用了旧版 `app/search.py`；部署当前已转义 FTS 查询的代码并重启 API，无需为此重建索引 |
| `Permission denied (publickey)` | 公钥装错 Linux 用户、私钥路径不对，或服务器不允许公钥认证 |
| 非交互连接仍需要私钥口令 | 给当前 Windows 用户的 SSH agent 加载密钥 |
| `Host key verification failed` | 先普通 SSH 登录并核对指纹；迁移导致密钥改变时按第 8.3 节处理 |
| MCP 初始化超时 / stdout 不是 JSON | 检查远端路径和依赖；非交互 shell 不要输出欢迎语，MCP stdout 专用于协议，日志写 stderr |
| `MCP tool call requires approval, but approval policy is never` | 补齐三个查询工具的 `approval_mode = "approve"`，然后新开 Codex 会话 |
| TOML duplicate table | 重复添加了同名服务或子表；合并而非反复追加 |
| Windows `codex.ps1` 被执行策略阻止 | 用 `codex.cmd` 或 CMD 运行 |
| 关闭 Linux SSH 窗口后不可用 | API 之前只在前台运行；按第 3 节设置常驻服务 |
| `Address already in use` | 端口已有 API 占用；检查现有进程或 systemd 服务，不要重复启动 |
| MCP 有连接但查询为空 | 检查文档是否已索引、能否提取文字，换用确定存在的简短关键词；当前不做语义检索 |
| 配置改了但行为没变 | 重新启动使用端的 Codex 会话，并确认改的是运行 Codex 那台机器的配置 |
| 新版/旧版 Codex 不识别字段 | 检查 `codex --version` 和官方文档；本机验收版本为 Codex CLI 0.167.0 |

## 10. 项目文件速查

| 文件 | 用途 |
|---|---|
| [本手册](MCP部署与Codex接入手册.md) | 从零部署、迁移和两端接入的统一入口 |
| [scripts/start_api.sh](scripts/start_api.sh) | 按 `.env` 启动 HTTP API |
| [scripts/mcp_stdio.sh](scripts/mcp_stdio.sh) | 启动 MCP stdio，供 Codex 本机或 SSH 调用 |
| [scripts/reindex.sh](scripts/reindex.sh) | 增量解析并更新索引 |
| [scripts/check_mcp.py](scripts/check_mcp.py) | 实际 MCP 协议与查询自检 |
| [configs/codex-mcp-local.toml](configs/codex-mcp-local.toml) | Linux 同机配置 |
| [configs/codex-mcp.toml](configs/codex-mcp.toml) | 使用 SSH 别名的通用配置 |
| [configs/codex-mcp-windows.toml](configs/codex-mcp-windows.toml) | 使用当前服务器 IP 的 Windows 示例 |
| [scripts/setup_codex_windows.ps1](scripts/setup_codex_windows.ps1) | 可选 Windows 配置辅助脚本 |

官方参考：[Codex MCP 配置](https://developers.openai.com/codex/mcp/)、[Codex CLI](https://developers.openai.com/codex/cli/)。
