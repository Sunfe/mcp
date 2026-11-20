# Windows 本地部署与 Codex 接入

适用：Windows 原生 Python、Codex CLI / App，所有文档、SQLite、API 和 MCP 均在本机运行。

```text
Windows Codex
  → powershell.exe scripts/mcp_stdio.ps1
  → .venv/Scripts/python.exe -m app.mcp_server
  → http://127.0.0.1:8016
  → 本机 knowledge.db 和 raw/
```

除特别标注外，以下命令在 PowerShell 的项目根目录执行。建立索引也可使用下文的 MSYS2 / Git Bash 或 WSL 命令。示例路径为 `D:\repo\mcp`；迁移时修改实际路径。与 SSH 方案不同，本方案需要本机 Python 和文档，不依赖 Ubuntu 或 SSH。

## 1. Python 与数据

项目当前固定依赖已在 Python 3.11.9 上验证。不要直接使用系统默认的 Python 3.15 安装这些旧版本依赖。

```powershell
py -0p
py -3.11 -m pip install --user uv
py -3.11 -m uv venv --python 3.11 .venv
py -3.11 -m uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

没有 `.env` 时复制 `.env.example` 并为 `API_TOKEN` 设置随机值。API 和 MCP 均从项目根目录 `.env` 读取配置，不需要把 Token 写进 Codex 配置。

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

上面的复制仅用于 `.env` 不存在的新机器；已有配置应保留。正常本地配置：

```dotenv
APP_HOST=127.0.0.1
APP_PORT=8016
RAW_DIR=raw
DB_PATH=knowledge.db
```

把文档完整放入 `raw/`。从 Linux 复制来的数据库可先备份，然后重建本地路径索引。路径变化会导致文档重新导入，`document_id` / `chunk_id` 也会变化。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\reindex.ps1
```

扫描版 PDF 不会自动 OCR。TXT、PDF、DOCX 使用 Python 依赖解析；旧版 `.doc` 还需要额外安装可用的 `antiword`，或先转换为 DOCX / PDF。

### 从 MSYS2 / Git Bash 建立索引

把需要保留的全部文档放进项目的 `raw/`，然后执行：

```bash
cd /d/repo/mcp
./.venv/Scripts/python.exe -X utf8 -u -m app.ingest
```

这会直接运行已安装项目依赖的 Windows Python，无需 PowerShell，也无需激活虚拟环境。`-X utf8` 启用 UTF-8，`-u` 让索引进度及时显示。已在 MSYS / Git Bash 下验证该解释器解析到 `D:\repo\mcp\raw` 和 `D:\repo\mcp\knowledge.db`。

### 从 WSL 建立索引

在已挂载 Windows D 盘且启用 Windows 程序互操作的 WSL 中执行：

```bash
cd /mnt/d/repo/mcp
./.venv/Scripts/python.exe -X utf8 -u -m app.ingest
```

这里仍使用 Windows 虚拟环境中的 `python.exe`，更新当前 Windows 服务读取的同一份数据库。WSL 运行 Windows 程序的机制见 [Microsoft 官方说明](https://learn.microsoft.com/en-us/windows/wsl/filesystems#run-windows-tools-from-linux)。本机尚未实跑这条 WSL 命令。

以上两种方式均从项目根目录的 `.env` 读取 `RAW_DIR` 和 `DB_PATH`。当前配置为 `raw` 和 `knowledge.db` 时，分别对应 `D:\repo\mcp\raw` 与 `D:\repo\mcp\knowledge.db`。无需改成 `/d/...` 或 `/mnt/d/...`，也无需重新安装依赖。

索引是增量更新：跳过未变化文件，导入新增或修改文件，并移除已从 `raw/` 删除的文件记录。因此 `raw/` 应保留所有仍需查询的文档。成功结束时会打印 `[DONE]` 及导入、未变、跳过和移除数量。

现有 `scripts/reindex.sh` 固定调用 `.venv/bin/python`，适用于 Linux 虚拟环境。当前 Windows 部署从 Bash 更新索引时使用上面的 `.venv/Scripts/python.exe` 命令；不要用 WSL 的 Linux Python 覆盖当前 Windows `.venv`。

## 2. 启动与登录自启

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1 -Action Status
Invoke-RestMethod http://127.0.0.1:8016/health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_mcp.ps1 -Query P5-35
```

`Start` 在隐藏窗口中启动 API，退出当前终端后仍运行；重复启动会报告已有的项目进程。API 启动完成前，健康检查可能暂时连接失败。日志写入 `logs/api.stdout.log` 和 `logs/api.stderr.log`，每次启动覆盖这两个运行日志。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1 -Action InstallAutostart
```

这会在当前 Windows 用户的启动目录创建 `MCP Knowledge Server.lnk`。以后登录 Windows 自动启动，无需管理员权限。它不是 Windows 系统服务，用户注销后不会继续提供服务。更换项目位置后需重新执行安装自启。

停止、修改代码后重启，或取消登录自启：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1 -Action Stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1 -Action Start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_api.ps1 -Action RemoveAutostart
```

启动脚本只管理本项目虚拟环境下的 `app.main` 进程树。`Status` 显示进程存在，协议自检才验证 API、鉴权和文档查询。

## 3. Codex 配置

将 [Windows 本地模板](../configs/codex-mcp-windows-local.toml) 合并到 `%USERPROFILE%\.codex\config.toml`；设置了 `CODEX_HOME` 时使用该目录。先备份，保留其他配置，同名服务和子表各保留一份。

修改模板中的项目路径 `D:\repo\mcp` 和 Windows 系统目录（若不是 `C:\Windows`）。命令使用 Windows PowerShell 的绝对路径；stdio 启动脚本会设置项目工作目录和 UTF-8，因此从其他工程打开 Codex 也能使用。

仅启用 `list_documents`、`search_documents`、`get_document` 三个查询工具，索引通过第 1 节的 PowerShell、MSYS / Git Bash 或 WSL 命令手动更新。

```powershell
codex.cmd mcp get knowledge-base
codex.cmd exec --ephemeral --sandbox read-only 'Use only knowledge-base MCP: call list_documents, then search_documents with query P5-35 and limit 2. Report actual results and document_id/chunk_id. Do not run shell commands or modify files.'
```

桌面 App 重新加载 MCP 配置或重启后，在新会话中输入：

> 请使用 knowledge-base 列出资料，再搜索 P5-35，limit=2，引用文档标题、document_id 和 chunk_id。

注册成功只表示配置已保存；应看到实际查询工具调用成功。当前已打开的聊天不会因修改配置自动增加工具。

### 让 Codex 优先查询 knowledge-base

在实际使用知识库的项目根目录，将下面的规则合并到现有 `AGENTS.md`，保留原有内容。Codex 会读取项目指令；OpenAI 的 [Docs MCP 官方说明](https://developers.openai.com/learn/docs-mcp) 也建议通过 `AGENTS.md` 约定自动使用指定 MCP。

```markdown
## 知识库查询顺序

- 涉及设备手册、伺服驱动器参数、通信协议或已归档项目资料时，回答或修改相关代码之前，先通过 knowledge-base MCP 查询依据，无需用户另行提醒。
- 优先调用 search_documents，使用型号、参数编号、寄存器地址或问题关键词检索。不了解已收录哪些资料时，先调用 list_documents。
- 必要时调用 get_document 补充上下文。回答中注明实际命中的文档标题、document_id 和 chunk_id，区分资料原文与推断。
- 没有命中时，用相关型号或关键词换一种查法；仍无结果，再查代码、其他文档或网络，并说明知识库没有找到依据。
- MCP 不可用时明确说明，继续使用可用来源，不得声称已经查过知识库或编造查询结果。
```

项目规则只用于该项目。如果希望所有项目都采用该顺序，可合并到当前 Codex 的全局 `AGENTS.md`：Windows 当前默认位置是 `C:\Users\liaozhic\.codex\AGENTS.md`；设置了 `CODEX_HOME` 时使用该目录。若实际运行的是 WSL 内的 Linux Codex，则使用那个环境的 `~/.codex/AGENTS.md`。

同一目录存在非空的 `AGENTS.override.md` 时，它优先于 `AGENTS.md`；应将规则合并到实际生效的文件。指令发现和作用范围见 [OpenAI 官方 AGENTS.md 说明](https://developers.openai.com/codex/guides/agents-md)。规则是对模型查询行为的约定，不能保证每次机械执行；需要严格验收时查看真实工具调用。

修改后在目标项目重新启动 Codex，用自然问题验证，例如“DS5L1 的 P5-35 参数有什么作用？”验收应看到 Codex 先实际调用 `knowledge-base.search_documents`，随后根据结果回答并引用片段编号。仅看到 `/mcp` 已连接不足以证明优先查询规则已生效。

## 4. 本次部署记录

2026-11-20，在 `D:\repo\mcp` 创建 Windows Python 3.11 虚拟环境，保留现有 `.env`，导入本机 DS5L1 手册共 324 个文本块。原数据库备份位于 `backups/knowledge-before-windows-20261120-095934.db`；Codex 配置备份位于 `C:\Users\liaozhic\.codex\config.toml.before-knowledge-base-local-20261120-095934`。

Windows MCP 协议检查已通过，`P5-35` 查询返回 `document_id=2`，示例 `chunk_id=473` / `476`。再次导入后编号可能变化，以实际返回为准。

本机 Codex CLI 0.167.0 已通过真实调用验收：`list_documents` 返回 1 份手册，`search_documents(query="P5-35", limit=2)` 返回上述两个片段，两个调用均成功，Codex 退出码为 0。回答保存于 `logs/codex-local-verification.txt`。现有 10 项单元测试全部通过。

补充验收：从 `D:\\liaozhic\\wksp\\chair753host` 新开 Codex CLI 0.167.0，使用现有 MCP 配置且不覆盖 `required`，`/mcp` 显示 `knowledge-base: connected (3 tools)`；在同一交互会话实际调用文档列表和 `P5-35` 搜索，返回 `document_id=2`、`chunk_id=473/476`。

已实际检查后台重复启动、停止进程树、通过登录自启快捷方式重新启动，并从项目外目录运行 Windows 协议自检。尚未注销或重启 Windows；已验证的是同一个自启快捷方式的实际执行。桌面 App 的已有聊天需重新加载配置后再使用。

## 5. 排错

- 连接失败：先检查 `logs/api.stderr.log`，再运行健康检查和 `check_mcp.ps1`。
- `/mcp` 显示 `cancelled`：先在当前会话再次执行 `/mcp`；若仍未连接，退出当前 Codex 后在同一目录重新启动，检查状态并实际调用查询工具。本次旧会话出现过 `cancelled (3 tools)`，新开的普通会话显示连接成功且查询成功；旧会话取消原因尚未确定，不能仅凭该状态认定 Python 服务故障。
- 端口被占用：查询 `Get-NetTCPConnection -State Listen -LocalPort 8016` 的进程；若改端口，修改 `.env` 后重启 API 和 Codex MCP。
- 权限错误：确认模板的三个 `approval_mode = "approve"` 子表已合并，再新开 Codex 会话。
- 中文显示不正常：通过仓库 PowerShell 脚本启动，它们会为 Python 设置 UTF-8。
- Windows 脚本被执行策略阻止：上面的 `-ExecutionPolicy Bypass` 只作用于该次 PowerShell 进程，不修改系统全局执行策略。
