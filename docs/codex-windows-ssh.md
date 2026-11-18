# Windows 11 Pro + Codex CLI 通过 SSH 查询知识库

服务器：`liaozhic@66.245.192.250`，SSH 端口 `22`，项目目录 `/home/liaozhic/data/mcp`。
你已能从 Windows 免密登录。接下来所有客户端命令都在 **Windows PowerShell** 执行，Codex 也在 Windows 上启动。

链路为：Windows Codex CLI → Windows `ssh.exe` → Linux MCP stdio → Linux `127.0.0.1:8016` API → 文档索引。

## 1. 下载并执行安装脚本

Windows 已安装 Codex CLI 并完成登录后，在 PowerShell 中执行：

```powershell
scp liaozhic@66.245.192.250:/home/liaozhic/data/mcp/scripts/setup_codex_windows.ps1 .\setup_codex_windows.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_codex_windows.ps1 -Verify
```

`ExecutionPolicy Bypass` 只作用于这一次脚本进程。脚本兼容 Windows PowerShell 5.1，不需要在 Windows 安装 Python，也不需要复制服务器 `.env` 或文档。

脚本会：

1. 检查 `ssh.exe` 和 Codex CLI，验证非交互密钥登录。
2. 经 SSH 在服务器执行真实 MCP 初始化、工具发现和 `P5-35` 查询。
3. 备份 Windows 用户的 Codex 配置，合并 `knowledge-base` 的 SSH 启动命令、超时和三个查询工具的权限；保留原有模型、登录及其他 MCP 配置。
4. 用 `codex exec` 在 Windows 实际调用知识库。只有看到两个工具都成功返回，才说明 Windows 到 MCP 的完整链路通过。

默认配置位置是 `$env:USERPROFILE\.codex\config.toml`；若已有 `CODEX_HOME`，脚本会使用该目录。脚本优先调用 `codex.cmd`，避免 PowerShell 对 npm `codex.ps1` 的执行策略限制。

重复执行会更新脚本自己添加的配置块。若已有手工配置的同名 `knowledge-base`，脚本会保留它，把新配置写到 `%TEMP%\codex-knowledge-base-ssh.toml`，提示你合并，避免重复 TOML 表。

使用其他 SSH 端口或私钥时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_codex_windows.ps1 -ServerAddress 66.245.192.250 -UserName liaozhic -Port 22 -IdentityFile "$env:USERPROFILE\.ssh\id_ed25519" -Verify
```

如果你平时依赖 `~/.ssh/config` 中的别名、跳板机或自定义密钥配置，传 `-ServerAddress 你的SSH别名`，并传入相同用户与端口。当前默认命令使用服务器 IP，不会匹配仅以别名定义的 SSH `Host` 配置。

## 2. 日常使用

在 **Windows** 新开终端和 Codex 会话：

```powershell
codex mcp get knowledge-base
codex
```

进入 Codex 后用 `/mcp` 查看 `knowledge-base`。然后直接问：

> 请使用 knowledge-base 的 list_documents 列出资料，再用 search_documents 搜索 P5-35，解释相关内容并引用文档标题、document_id 和 chunk_id。

当前资料库有一份 DS5L1 伺服驱动器手册。服务器本机已验证搜索 `P5-35` 能返回片段，例如 `document_id=1`、`chunk_id=149` / `152`。

MCP 进程由 Windows Codex 通过 SSH 自动启动；API 需保持在服务器运行。若 API 停止，可在服务器运行 `bash /home/liaozhic/data/mcp/scripts/start_api.sh`，或由已有服务管理方式保持运行。服务器退出终端后也要继续提供服务时，请使用 systemd 等进程管理方式保持 API 运行。

## 3. 手工配置

也可以下载完整模板并合并到 Windows Codex 配置：

```powershell
scp liaozhic@66.245.192.250:/home/liaozhic/data/mcp/configs/codex-mcp-windows.toml .\codex-mcp-windows.toml
```

同名 `[mcp_servers.knowledge-base]` 及其工具子表只能各有一份。模板使用 `command = "ssh.exe"`，参数中包含服务器登录地址和远程 Bash 命令。三个查询工具配置为自动允许调用，`reindex_documents` 未启用。

Windows 不需要 API Token，也不需要 SSH 端口转发。服务器 API 保持 `127.0.0.1:8016` 即可，SSH 负责连接到远端 MCP 进程。

## 4. 排错

先独立验证 SSH 与服务端：

```powershell
ssh -T -o BatchMode=yes -o ConnectTimeout=10 liaozhic@66.245.192.250 true
ssh -T -o BatchMode=yes liaozhic@66.245.192.250 "/home/liaozhic/data/mcp/.venv/bin/python /home/liaozhic/data/mcp/scripts/check_mcp.py --query P5-35"
```

- `Permission denied (publickey)`：检查 Windows SSH 选择的密钥；可给安装脚本传 `-IdentityFile`，有口令的密钥须加载到 Windows SSH agent。
- `Host key verification failed`：先普通 SSH 登录，核对服务器指纹后确认。脚本不会跳过主机验证。
- 远端自检报 API 连接失败：检查服务器 8016 服务，先恢复 API 再运行安装脚本。
- `codex.ps1 cannot be loaded`：使用 `codex.cmd`，或从 CMD 运行 Codex。
- `MCP tool call requires approval, but approval policy is never`：确认三个查询工具的 `approval_mode = "approve"` 子表已写入，并新开 Codex 会话。
- Codex 不识别 MCP 权限字段或命令选项：检查 Windows `codex --version`，升级到支持这些字段的当前版本；本项目在服务器 Codex CLI 0.167.0 上已验证。
- SSH 命令能运行，但 Codex 报协议解析错误：非交互 SSH 的 stdout 只能包含 MCP JSON-RPC；服务器 shell 启动脚本的欢迎语等额外输出需要写到 stderr 或仅在交互 shell 输出。

参考：<https://developers.openai.com/codex/mcp/>。
