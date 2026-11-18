> 同机 Codex CLI 已跑通。Windows 11 Pro + Codex CLI 通过 SSH 连接本服务器，请使用 [Windows 安装与验收说明](docs/codex-windows-ssh.md)、[PowerShell 安装脚本](scripts/setup_codex_windows.ps1) 和 [Windows 配置模板](configs/codex-mcp-windows.toml)。同机配置仍见 [实际接入说明](docs/codex-mcp.md)。实际服务器路径为 `/home/liaozhic/data/mcp`，API 端口为 `8016`。下文保留原始方案，其中 `/opt/mcp-knowledge`、`8000` 和示例 SSH 地址不是本项目的实际配置。
>
> 当前依赖 FastMCP 0.4.1 仅支持 stdio / SSE，不支持下文可选示例中的 `streamable-http` 参数；本次接入使用 stdio，无需升级。

可以。你这套服务接入 **Codex / opencode / Claude Code** 时，核心有两种方式：

1. **最推荐：stdio MCP，通过 SSH 远程启动你的 MCP Server**
2. **可选：HTTP/SSE MCP，公网暴露 MCP Endpoint**

对你当前这套架构来说，我最推荐第 1 种：  
**Codex / opencode / Claude Code 在本地运行，但通过 SSH 启动服务器上的 MCP 进程。**

这样有几个好处：

- 不需要把 MCP 端口暴露到公网
- 安全性更高
- Claude Code / Codex CLI / opencode 对 stdio MCP 支持更普遍
- 你的 MCP Server 仍然在服务器上运行，可以访问服务器本地的 `127.0.0.1:8000` FastAPI 服务

---

# 一、先整理一下当前架构

你现在服务器上有：

```text
/opt/mcp-knowledge
├── app/
│   ├── main.py          # FastAPI HTTP API
│   ├── mcp_server.py    # MCP Server，stdio 模式
│   └── ...
├── raw/
├── data/
├── .env
└── .venv/
```

FastAPI 服务：

```bash
127.0.0.1:8000
```

MCP 服务：

```bash
python -m app.mcp_server
```

你的 `mcp_server.py` 里面会调用：

```python
http://127.0.0.1:8000/api/search
http://127.0.0.1:8000/api/documents
```

所以只要 MCP 进程运行在服务器上，它就可以正常访问本地 API。

---

# 二、推荐接入方式：stdio MCP + SSH

## 1. 在服务器上创建 MCP 启动脚本

在服务器执行：

```bash
cat > /opt/mcp-knowledge/scripts/mcp_stdio.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd /opt/mcp-knowledge
exec /opt/mcp-knowledge/.venv/bin/python -m app.mcp_server
EOF

chmod +x /opt/mcp-knowledge/scripts/mcp_stdio.sh
```

这个脚本的作用是：

```bash
cd /opt/mcp-knowledge
python -m app.mcp_server
```

但封装成脚本后，Codex / opencode / Claude Code 配置起来更简单。

---

## 2. 确保 FastAPI 服务在服务器上已启动

如果你已经配置了 systemd：

```bash
sudo systemctl status mcp-knowledge-api
```

如果没有启动：

```bash
sudo systemctl start mcp-knowledge-api
```

测试：

```bash
curl http://127.0.0.1:8000/health
```

应该返回类似：

```json
{
  "status": "ok",
  "service": "MCP Knowledge Server"
}
```

---

## 3. 在你本地机器配置 SSH 免密登录

假设服务器用户是 `ubuntu`，服务器域名或 IP 是：

```text
your-server.com
```

本地执行：

```bash
ssh-keygen -t ed25519
```

然后把公钥复制到服务器：

```bash
ssh-copy-id ubuntu@your-server.com
```

测试：

```bash
ssh ubuntu@your-server.com
```

如果不需要输入密码，说明 OK。

---

## 4. 测试远程 MCP 启动命令

在你的本地机器上执行：

```bash
ssh -T ubuntu@your-server.com /opt/mcp-knowledge/scripts/mcp_stdio.sh
```

正常情况下它可能不会输出内容，而是一直等待 MCP JSON-RPC 输入。

这说明它正在以 stdio MCP 模式运行。

如果你看到 Python 报错，需要先修复。

---

# 三、接入 Claude Code

Claude Code 对 MCP 支持比较好，推荐用 stdio 方式接。

## 方式一：使用 `claude mcp add-json`

在本地执行：

```bash
claude mcp add-json knowledge-base '{
  "type": "stdio",
  "command": "ssh",
  "args": [
    "-T",
    "-o", "LogLevel=ERROR",
    "-o", "BatchMode=yes",
    "ubuntu@your-server.com",
    "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
  ]
}'
```

把：

```text
ubuntu@your-server.com
```

换成你的服务器 SSH 登录地址。

---

## 方式二：使用 `claude mcp add`

也可以这样：

```bash
claude mcp add knowledge-base -- ssh -T -o LogLevel=ERROR -o BatchMode=yes ubuntu@your-server.com /opt/mcp-knowledge/scripts/mcp_stdio.sh
```

---

## 查看是否添加成功

```bash
claude mcp list
```

进入 Claude Code 后，也可以输入：

```text
/mcp
```

一般可以看到已连接的 MCP Server。

---

## 在 Claude Code 里使用

你可以直接问：

```text
请使用 knowledge-base 知识库搜索“员工请假制度”，并总结相关规定。
```

或者：

```text
请先调用 MCP 工具 search_documents 查询“产品接口鉴权方式”，然后基于检索结果回答。
```

你的 MCP 工具大概率会显示为：

```text
search_documents
get_document
list_documents
reindex_documents
```

有些客户端会显示成类似：

```text
mcp__knowledge-base__search_documents
```

---

# 四、接入 Codex / Codex CLI

这里我假设你说的是 **OpenAI Codex CLI / Codex Agent 本地工具**。  
如果你说的是其他 Codex 环境，需要看它是否支持自定义 MCP。

Codex CLI 常见 MCP 配置文件是：

```bash
~/.codex/config.toml
```

如果没有就创建：

```bash
mkdir -p ~/.codex
nano ~/.codex/config.toml
```

加入：

```toml
[mcp_servers.knowledge-base]
command = "ssh"
args = [
  "-T",
  "-o", "LogLevel=ERROR",
  "-o", "BatchMode=yes",
  "ubuntu@your-server.com",
  "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
]
startup_timeout_sec = 30
tool_timeout_sec = 120
```

然后重启 Codex CLI。

---

## 如果 Codex 和 MCP Server 在同一台服务器上

如果你是在服务器本机运行 Codex，不需要 SSH，可以这样：

```toml
[mcp_servers.knowledge-base]
command = "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

---

## 给 Codex 增加使用说明

建议在你的项目根目录放一个：

```bash
AGENTS.md
```

内容可以写：

```markdown
# Knowledge Base Usage

本项目可使用 MCP 服务器 `knowledge-base` 查询内部资料。

当问题涉及以下内容时，请优先调用 MCP 工具：

- 公司制度
- 产品文档
- 接口说明
- 项目资料
- 历史文档
- PDF / DOCX / TXT 资料库内容

推荐流程：

1. 使用 `search_documents(query, limit)` 检索相关片段。
2. 如有必要，使用 `get_document(document_id)` 获取完整文档。
3. 回答时请尽量引用文档标题、document_id、chunk_id。
4. 不要编造知识库中没有的内容。
```

这样 Codex 更容易知道什么时候该调用 MCP。

---

# 五、接入 opencode

opencode 也可以通过 MCP 接本地或远程 stdio 服务。

不同版本的 opencode 配置格式可能略有差异，但常见是 `opencode.json`。

你可以在项目根目录创建：

```bash
opencode.json
```

示例：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "knowledge-base": {
      "type": "local",
      "command": "ssh",
      "args": [
        "-T",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=yes",
        "ubuntu@your-server.com",
        "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
      ],
      "enabled": true
    }
  }
}
```

如果你的 opencode 版本使用数组形式的 command，则可以改成：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "knowledge-base": {
      "type": "local",
      "command": [
        "ssh",
        "-T",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=yes",
        "ubuntu@your-server.com",
        "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
      ],
      "enabled": true
    }
  }
}
```

---

## 如果 opencode 和 MCP Server 在同一台服务器上

配置可以简化为：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "knowledge-base": {
      "type": "local",
      "command": "/opt/mcp-knowledge/scripts/mcp_stdio.sh",
      "enabled": true
    }
  }
}
```

---

## 给 opencode 增加使用说明

同样建议在项目中放一个：

```bash
AGENTS.md
```

内容：

```markdown
# MCP 知识库使用说明

你可以通过 MCP Server `knowledge-base` 访问内部资料库。

当用户询问制度、产品文档、项目资料、接口说明、PDF/DOCX/TXT 文档内容时，优先使用：

- `search_documents`
- `get_document`
- `list_documents`

回答时请基于检索结果，不要编造。
```

---

# 六、可选方案：远程 HTTP/SSE MCP

如果你不想用 SSH，也可以把 MCP Server 作为 HTTP/SSE 服务暴露出来。

但是我不建议一开始这么做，原因是：

- 远程 MCP 传输协议不同客户端支持程度不一样
- 鉴权处理更复杂
- 暴露到公网需要额外安全措施
- stdio + SSH 更稳定

不过如果你确实需要远程 HTTP MCP，可以这样做。

---

## 1. 新增一个 HTTP MCP Server

新建：

```bash
nano /opt/mcp-knowledge/app/mcp_http_server.py
```

内容示例：

```python
import httpx
from fastmcp import FastMCP
from app.config import settings

mcp = FastMCP("KnowledgeBaseMCP")

BASE_URL = f"http://{settings.app_host}:{settings.app_port}"
HEADERS = {"Authorization": f"Bearer {settings.api_token}"}


@mcp.tool()
def list_documents() -> dict:
    resp = httpx.get(
        f"{BASE_URL}/api/documents",
        headers=HEADERS,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def search_documents(query: str, limit: int = 5) -> dict:
    limit = min(limit, settings.max_search_limit)
    resp = httpx.post(
        f"{BASE_URL}/api/search",
        headers=HEADERS,
        json={"query": query, "limit": limit},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_document(document_id: int) -> dict:
    resp = httpx.get(
        f"{BASE_URL}/api/documents/{document_id}",
        headers=HEADERS,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def reindex_documents(full: bool = False) -> dict:
    resp = httpx.post(
        f"{BASE_URL}/api/reindex",
        headers=HEADERS,
        json={"full": full},
        timeout=300
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    # 具体参数取决于 fastmcp 版本
    # 新版本 FastMCP 通常支持 streamable-http 或 sse
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=9001,
        path="/mcp"
    )
```

注意：  
不同版本 `fastmcp` 对 HTTP/SSE 的参数可能不同。

如果你运行时报错，可以查看：

```bash
python -c "import fastmcp; print(fastmcp.__version__)"
```

必要时升级：

```bash
pip install -U fastmcp
```

---

## 2. systemd 服务

```bash
sudo nano /etc/systemd/system/mcp-knowledge-http-mcp.service
```

内容：

```ini
[Unit]
Description=MCP Knowledge HTTP MCP Service
After=network.target mcp-knowledge-api.service
Requires=mcp-knowledge-api.service

[Service]
User=ubuntu
WorkingDirectory=/opt/mcp-knowledge
Environment="PATH=/opt/mcp-knowledge/.venv/bin"
ExecStart=/opt/mcp-knowledge/.venv/bin/python -m app.mcp_http_server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-knowledge-http-mcp
sudo systemctl start mcp-knowledge-http-mcp
```

---

## 3. Nginx 暴露 MCP

假设 HTTP MCP 在：

```text
127.0.0.1:9001
```

Nginx 加：

```nginx
location /mcp {
    proxy_pass http://127.0.0.1:9001/mcp;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    proxy_read_timeout 3600;
    proxy_send_timeout 3600;
    proxy_buffering off;
}
```

如果是 SSE，还要类似：

```nginx
location /sse {
    proxy_pass http://127.0.0.1:9001/sse;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    proxy_read_timeout 3600;
    proxy_send_timeout 3600;
    proxy_buffering off;
}
```

---

## 4. Claude Code 接 HTTP MCP

如果你的 Claude Code 版本支持 HTTP MCP，可以类似：

```bash
claude mcp add --transport http knowledge-base https://your-domain.com/mcp
```

如果是 SSE：

```bash
claude mcp add --transport sse knowledge-base https://your-domain.com/sse
```

不过我还是建议优先使用：

```bash
stdio + ssh
```

更稳定。

---

# 七、三种接入方式对比

| 方式 | 推荐程度 | 适合场景 | 安全性 | 稳定性 |
|---|---:|---|---:|---:|
| 本机 stdio | 高 | Codex/opencode/Claude Code 和服务在同一台机器 | 高 | 高 |
| SSH stdio | 最高 | 本地开发机连接远程服务器 | 高 | 高 |
| HTTP/SSE MCP | 中 | 客户端必须远程 HTTP MCP | 取决于鉴权 | 中 |
| 直接 HTTP API | 高 | 自己写 Agent / RAG 应用 | 高 | 高 |

你的情况最适合：

```text
Claude Code / Codex / opencode
        |
        | stdio MCP
        |
      ssh
        |
        v
远程服务器 /opt/mcp-knowledge/scripts/mcp_stdio.sh
        |
        v
app.mcp_server
        |
        v
127.0.0.1:8000 FastAPI
        |
        v
SQLite / 文档索引
```

---

# 八、最推荐的最终配置

## Claude Code

```bash
claude mcp add-json knowledge-base '{
  "type": "stdio",
  "command": "ssh",
  "args": [
    "-T",
    "-o", "LogLevel=ERROR",
    "-o", "BatchMode=yes",
    "ubuntu@your-server.com",
    "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
  ]
}'
```

---

## Codex CLI

`~/.codex/config.toml`：

```toml
[mcp_servers.knowledge-base]
command = "ssh"
args = [
  "-T",
  "-o", "LogLevel=ERROR",
  "-o", "BatchMode=yes",
  "ubuntu@your-server.com",
  "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
]
startup_timeout_sec = 30
tool_timeout_sec = 120
```

---

## opencode

`opencode.json`：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "knowledge-base": {
      "type": "local",
      "command": "ssh",
      "args": [
        "-T",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=yes",
        "ubuntu@your-server.com",
        "/opt/mcp-knowledge/scripts/mcp_stdio.sh"
      ],
      "enabled": true
    }
  }
}
```

---

# 九、常见问题

## 1. MCP 连接不上

先本地测试：

```bash
ssh -T ubuntu@your-server.com /opt/mcp-knowledge/scripts/mcp_stdio.sh
```

如果有报错，先修报错。

---

## 2. SSH 需要密码

MCP 客户端通常不能交互输入密码。

必须配置 SSH key 免密登录。

---

## 3. SSH 登录时输出欢迎信息导致 MCP 失败

MCP stdio 要求 stdout 只能输出 MCP JSON-RPC 内容。

如果你的服务器 SSH 登录时有乱七八糟的输出，比如：

```text
Welcome to Ubuntu
Last login: ...
```

可能会干扰 MCP。

解决：

- 使用 `ssh -T`
- 使用 `-o LogLevel=ERROR`
- 确保 `.bashrc` / `.profile` 里面没有 `echo`
- 不要在 `mcp_stdio.sh` 里面 `echo`

---

## 4. MCP 工具能连上，但搜索没有结果

检查索引：

```bash
sqlite3 /opt/mcp-knowledge/data/knowledge.db
```

执行：

```sql
SELECT count(*) FROM documents;
SELECT count(*) FROM chunks;
.quit
```

如果都是 0，说明还没有成功导入文档。

重新索引：

```bash
cd /opt/mcp-knowledge
source .venv/bin/activate
python -m app.ingest
```

---

## 5. Claude Code / Codex / opencode 不主动调用 MCP

这很常见。

你需要在提示词里明确说：

```text
请先使用 knowledge-base MCP 的 search_documents 工具查询相关资料，再回答。
```

也建议在项目中添加：

- Claude Code：`CLAUDE.md`
- Codex：`AGENTS.md`
- opencode：`AGENTS.md` 或项目说明文件

---

# 十、建议你添加一个 CLAUDE.md / AGENTS.md

在你的代码项目根目录创建：

```markdown
# 知识库 MCP 使用规则

本项目已配置 MCP Server：`knowledge-base`。

当用户问题涉及以下内容时，必须优先使用知识库 MCP：

- 公司制度
- 产品文档
- 技术文档
- API 说明
- 历史项目资料
- PDF / DOC / DOCX / TXT 文档内容

推荐调用流程：

1. 使用 `search_documents(query, limit=5)` 搜索相关资料。
2. 如果搜索结果不足，再使用 `list_documents()` 查看文档列表。
3. 如需完整上下文，使用 `get_document(document_id)`。
4. 回答时引用文档标题、document_id、chunk_id。
5. 如果知识库中没有找到答案，请明确说明“资料库中未找到相关内容”，不要编造。
```

这样 Codex / opencode / Claude Code 更容易主动使用你的 MCP 工具。

---

# 十一、我的最终建议

你现在应该采用这个方案：

```text
MCP Client：Claude Code / Codex / opencode
        |
        | stdio MCP
        |
        v
ssh ubuntu@your-server.com /opt/mcp-knowledge/scripts/mcp_stdio.sh
        |
        v
服务器上的 MCP Server
        |
        v
127.0.0.1:8000 FastAPI
        |
        v
SQLite FTS 知识库
```

这是目前最稳、最安全、最容易排障的接入方式。
