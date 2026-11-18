## GPT-5.4
下面给你一套**生产级升级版**，核心目标：

- **Ubuntu 22.04** 从零搭建
- 原始资料放到服务器
- 支持 **TXT / PDF / DOCX / DOC**
- 提供 **HTTP API + MCP 双接口**
- 支持 **Token 鉴权**
- 支持 **增量索引**
- 默认先用 **SQLite FTS5**（最稳、最省心）
- 可选升级到 **Qdrant 向量检索**
- 使用 **systemd + Nginx + HTTPS**

我会给你：
1. 整体架构
2. 完整项目目录
3. 可运行代码
4. 部署命令
5. systemd / nginx 配置
6. 后续升级到 Qdrant 的方式

---

# 一、最终架构

推荐你先落地这个版本：

```text
[原始文档 raw/]
      |
      v
[ingest 索引程序]
  - 提取文本
  - 切块
  - 写 SQLite
  - 建全文索引
      |
      v
[FastAPI 服务]
  - /api/search
  - /api/documents
  - /api/reindex
  - Token 鉴权
      |
      +----> [MCP Server]
                - tool: search_documents
                - tool: get_document
                - tool: list_documents
      |
      v
[Nginx + HTTPS]
      |
      v
[公网访问]
```

---

# 二、先说技术选型

## 当前版本使用
- Python 3.10+
- FastAPI
- Uvicorn
- SQLite FTS5
- MCP Python / FastMCP
- PyMuPDF / pypdf
- python-docx
- antiword / libreoffice
- systemd
- nginx

## 为什么先不用 Qdrant
因为你现在最重要的是：
> 先把“可生产运行、可访问、可重建索引、可鉴权”的系统跑起来。

SQLite FTS 非常适合第一阶段上线。  
后续我会再告诉你怎么平滑升级到 Qdrant。

---

# 三、项目目录结构

在服务器上我们建立：

```bash
/opt/mcp-knowledge/
├── app/
│   ├── main.py
│   ├── mcp_server.py
│   ├── ingest.py
│   ├── db.py
│   ├── parsers.py
│   ├── search.py
│   ├── auth.py
│   ├── config.py
│   └── schemas.py
├── raw/
│   ├── hr/
│   ├── product/
│   └── project/
├── data/
│   └── knowledge.db
├── logs/
├── scripts/
│   └── reindex.sh
├── .env
├── requirements.txt
└── .venv/
```

---

# 四、从零安装环境

## 1）安装系统依赖
```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  python3 python3-pip python3-venv \
  sqlite3 libsqlite3-dev \
  git curl wget unzip \
  build-essential software-properties-common \
  antiword poppler-utils libreoffice \
  nginx apache2-utils
```

如果你后面有扫描 PDF，再补 OCR：
```bash
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
```

---

## 2）创建项目目录
```bash
sudo mkdir -p /opt/mcp-knowledge
sudo chown -R $USER:$USER /opt/mcp-knowledge
cd /opt/mcp-knowledge

mkdir -p app raw data logs scripts
mkdir -p raw/hr raw/product raw/project
```

---

## 3）创建虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 4）创建 requirements.txt

创建文件：

```bash
cat > /opt/mcp-knowledge/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
python-dotenv==1.0.1
mcp==1.1.2
fastmcp==0.4.1
pypdf==5.0.1
pymupdf==1.24.10
python-docx==1.1.2
httpx==0.27.2
EOF
```

安装：
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

# 五、配置文件

创建 `.env`：

```bash
cat > /opt/mcp-knowledge/.env << 'EOF'
APP_NAME=MCP Knowledge Server
APP_HOST=127.0.0.1
APP_PORT=8000
API_TOKEN=replace_with_a_strong_token
RAW_DIR=/opt/mcp-knowledge/raw
DB_PATH=/opt/mcp-knowledge/data/knowledge.db
LOG_LEVEL=info
DEFAULT_SEARCH_LIMIT=5
MAX_SEARCH_LIMIT=20
CHUNK_SIZE=800
CHUNK_OVERLAP=100
EOF
```

生成一个强随机 Token：
```bash
python3 - << 'EOF'
import secrets
print(secrets.token_urlsafe(32))
EOF
```

把输出替换到 `.env` 中的 `API_TOKEN`。

---

# 六、完整代码

下面这些代码你直接复制即可。

---

## 1）app/config.py
```python
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv("/opt/mcp-knowledge/.env")


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "MCP Knowledge Server")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    api_token: str = os.getenv("API_TOKEN", "replace_me")
    raw_dir: str = os.getenv("RAW_DIR", "/opt/mcp-knowledge/raw")
    db_path: str = os.getenv("DB_PATH", "/opt/mcp-knowledge/data/knowledge.db")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    default_search_limit: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "5"))
    max_search_limit: int = int(os.getenv("MAX_SEARCH_LIMIT", "20"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))


settings = Settings()
```

---

## 2）app/auth.py
```python
from fastapi import Header, HTTPException, status
from app.config import settings


def verify_token(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return True
```

---

## 3）app/db.py
```python
import sqlite3
from app.config import settings


def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        file_type TEXT,
        category TEXT,
        file_mtime REAL,
        file_size INTEGER,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        source_info TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        content,
        chunk_id UNINDEXED,
        document_id UNINDEXED
    )
    """)

    conn.commit()
    conn.close()
```

---

## 4）app/parsers.py
```python
from pathlib import Path
from pypdf import PdfReader
from docx import Document
import subprocess
import fitz


def extract_text_from_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_pdf(path: Path) -> str:
    # 优先使用 pymupdf
    try:
        doc = fitz.open(str(path))
        texts = []
        for page in doc:
            texts.append(page.get_text("text"))
        full = "\n".join(texts).strip()
        if full:
            return full
    except Exception:
        pass

    # 回退 pypdf
    try:
        reader = PdfReader(str(path))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def extract_text_from_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_doc(path: Path) -> str:
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            errors="ignore"
        )
        return result.stdout
    except Exception:
        return ""


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return extract_text_from_txt(path)
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".doc":
        return extract_text_from_doc(path)
    return ""
```

---

## 5）app/search.py
```python
from contextlib import closing

from app.db import get_conn


def list_documents():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, path, file_type, category, file_size, updated_at
        FROM documents
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_document(document_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, path, file_type, category, file_size, updated_at
        FROM documents
        WHERE id = ?
    """, (document_id,))
    doc = cur.fetchone()
    if not doc:
        conn.close()
        return None

    cur.execute("""
        SELECT chunk_index, content, source_info
        FROM chunks
        WHERE document_id = ?
        ORDER BY chunk_index ASC
    """, (document_id,))
    chunks = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "document": dict(doc),
        "chunks": chunks,
        "content": "\n".join(c["content"] for c in chunks)
    }


def search_documents(query: str, limit: int = 5):
    terms = query.split()
    if not terms:
        return []

    # MATCH parses its own syntax even with SQL parameters. Quote each term as text.
    fts_query = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)

    sql = """
    SELECT c.id AS chunk_id,
           d.id AS document_id,
           d.title,
           d.category,
           c.chunk_index,
           c.content
    FROM chunks_fts f
    JOIN chunks c ON c.id = f.chunk_id
    JOIN documents d ON d.id = c.document_id
    WHERE chunks_fts MATCH ?
    LIMIT ?
    """
    with closing(get_conn()) as conn:
        rows = conn.execute(sql, (fts_query, limit)).fetchall()
        return [dict(row) for row in rows]
```

---

## 6）app/schemas.py
```python
from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


class ReindexRequest(BaseModel):
    full: Optional[bool] = False
```

---

## 7）app/ingest.py
```python
from pathlib import Path
from datetime import datetime
import os

from app.config import settings
from app.db import get_conn, init_db
from app.parsers import extract_text


def chunk_text(text: str, chunk_size: int, overlap: int):
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def file_category(path: Path, raw_dir: Path) -> str:
    try:
        rel = path.relative_to(raw_dir)
        if len(rel.parts) > 1:
            return rel.parts[0]
    except Exception:
        pass
    return "default"


def ingest_one(conn, path: Path, raw_dir: Path):
    stat = path.stat()
    text = extract_text(path)

    if not text.strip():
        print(f"[SKIP] empty or unsupported: {path}")
        return

    title = path.name
    category = file_category(path, raw_dir)
    now = datetime.utcnow().isoformat()

    cur = conn.cursor()

    cur.execute("SELECT id, file_mtime, file_size FROM documents WHERE path = ?", (str(path),))
    old = cur.fetchone()

    if old and float(old[1]) == float(stat.st_mtime) and int(old[2]) == int(stat.st_size):
        print(f"[UNCHANGED] {path}")
        return

    if old:
        document_id = old[0]
        cur.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        cur.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
        cur.execute("""
            UPDATE documents
            SET title=?, file_type=?, category=?, file_mtime=?, file_size=?, updated_at=?
            WHERE id=?
        """, (
            title, path.suffix.lower(), category, stat.st_mtime, stat.st_size, now, document_id
        ))
    else:
        cur.execute("""
            INSERT INTO documents (title, path, file_type, category, file_mtime, file_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title, str(path), path.suffix.lower(), category, stat.st_mtime, stat.st_size, now
        ))
        document_id = cur.lastrowid

    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)

    for idx, chunk in enumerate(chunks):
        cur.execute("""
            INSERT INTO chunks (document_id, chunk_index, content, source_info)
            VALUES (?, ?, ?, ?)
        """, (document_id, idx, chunk, ""))

        chunk_id = cur.lastrowid
        cur.execute("""
            INSERT INTO chunks_fts (content, chunk_id, document_id)
            VALUES (?, ?, ?)
        """, (chunk, chunk_id, document_id))

    conn.commit()
    print(f"[INGESTED] {path} chunks={len(chunks)}")


def remove_deleted_files(conn, existing_paths: set):
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM documents")
    rows = cur.fetchall()

    for row in rows:
        doc_id, path = row
        if path not in existing_paths:
            cur.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM chunks_fts WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            print(f"[REMOVED] {path}")

    conn.commit()


def run_ingest(full: bool = False):
    init_db()

    raw_dir = Path(settings.raw_dir)
    conn = get_conn()

    files = []
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in [".txt", ".pdf", ".docx", ".doc"]:
            files.append(path)

    existing_paths = {str(p) for p in files}

    if full:
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks")
        cur.execute("DELETE FROM chunks_fts")
        cur.execute("DELETE FROM documents")
        conn.commit()
        print("[FULL REINDEX] cleared database")

    for path in files:
        ingest_one(conn, path, raw_dir)

    remove_deleted_files(conn, existing_paths)
    conn.close()


if __name__ == "__main__":
    run_ingest(full=False)
```

---

## 8）app/main.py
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.config import settings
from app.auth import verify_token
from app.schemas import SearchRequest, ReindexRequest
from app.search import list_documents, get_document, search_documents
from app.ingest import run_ingest
from app.db import init_db

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/documents", dependencies=[Depends(verify_token)])
def api_list_documents():
    return {"items": list_documents()}


@app.get("/api/documents/{document_id}", dependencies=[Depends(verify_token)])
def api_get_document(document_id: int):
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@app.post("/api/search", dependencies=[Depends(verify_token)])
def api_search(req: SearchRequest):
    limit = req.limit or settings.default_search_limit
    limit = min(limit, settings.max_search_limit)
    results = search_documents(req.query, limit)
    return {"query": req.query, "items": results}


@app.post("/api/reindex", dependencies=[Depends(verify_token)])
def api_reindex(req: ReindexRequest):
    run_ingest(full=req.full or False)
    return JSONResponse({"status": "ok", "full": req.full or False})
```

---

## 9）app/mcp_server.py
这里我给你一个**实用型版本**：MCP 工具不直接碰数据库，而是通过 HTTP API 调 FastAPI 主服务。这样更稳，权限也统一。

```python
import httpx
from fastmcp import FastMCP
from app.config import settings

mcp = FastMCP("KnowledgeBaseMCP")

BASE_URL = f"http://{settings.app_host}:{settings.app_port}"
HEADERS = {"Authorization": f"Bearer {settings.api_token}"}


@mcp.tool()
def list_documents() -> dict:
    resp = httpx.get(f"{BASE_URL}/api/documents", headers=HEADERS, timeout=30)
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
    mcp.run()
```

---

## 10）scripts/reindex.sh
```bash
#!/usr/bin/env bash
set -e
cd /opt/mcp-knowledge
source .venv/bin/activate
python -m app.ingest
```

给执行权限：
```bash
chmod +x /opt/mcp-knowledge/scripts/reindex.sh
```

---

# 七、放入你的资料

把你的文档放到：
```bash
/opt/mcp-knowledge/raw/
```

例如：
```bash
/opt/mcp-knowledge/raw/hr/员工手册.pdf
/opt/mcp-knowledge/raw/product/产品说明.docx
/opt/mcp-knowledge/raw/project/项目记录.txt
```

---

# 八、首次建立索引

使用本仓库时，先进入项目根目录，检查根目录 `.env` 中的 `RAW_DIR` 和 `DB_PATH`。
当前代码会将相对路径解析为相对于项目根目录的路径，绝对路径也可以使用。例如：

```dotenv
RAW_DIR=raw
DB_PATH=data/knowledge.db
```

`RAW_DIR` 必须是实际存放文档的目录，支持递归扫描 `.txt`、`.pdf`、`.docx`、`.doc`。
`DB_PATH` 的父目录需要已存在；如果已有数据库，请保留原来的数据库位置，例如 `DB_PATH=knowledge.db`。
系统环境变量优先于 `.env`，修改配置后请重新运行命令，并检查输出中的实际路径。

```bash
cd /opt/mcp-knowledge
source .venv/bin/activate
python -m app.ingest
```

项目已创建虚拟环境时，也可以在项目根目录直接运行 `.venv/bin/python -m app.ingest`。
还可以执行 `bash scripts/reindex.sh`，脚本会自动定位项目目录并使用项目的虚拟环境。

如果成功，你会看到类似：
```bash
[START] RAW_DIR=/opt/mcp-knowledge/raw
[START] DB_PATH=/opt/mcp-knowledge/data/knowledge.db
[SCAN] Looking for .txt, .pdf, .docx, .doc files...
[SCAN] Found 2 supported file(s)
[PARSING] /opt/mcp-knowledge/raw/hr/员工手册.pdf
[INGESTED] /opt/mcp-knowledge/raw/hr/员工手册.pdf chunks=18
[PARSING] /opt/mcp-knowledge/raw/product/产品说明.docx
[INGESTED] /opt/mcp-knowledge/raw/product/产品说明.docx chunks=12
[DONE] files=2 ingested=2 unchanged=0 skipped=0 removed=0
```

该命令执行一次文档解析和 SQLite 索引后退出，不会启动 HTTP / MCP 服务，也不会自动监听文件变化。
解析结果写入 `DB_PATH` 指定的数据库，不会在 `raw/` 中生成新文件。
重复执行时，未修改的文档会显示 `[UNCHANGED]`，不会重复解析。
目录不存在或不是目录时会显示 `[ERROR]` 并以非零状态退出，同时保留已有索引；目录有效但没有支持的文档时会显示 `[WARNING]`。
`[SKIP] no text extracted` 表示没有提取到文本，请检查文档内容；扫描版 PDF 需要另外进行 OCR，当前解析器不会自动 OCR。

---

# 九、启动 HTTP 服务

```bash
cd /opt/mcp-knowledge
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

测试健康检查：
```bash
curl http://127.0.0.1:8000/health
```

应该返回：
```json
{"status":"ok","service":"MCP Knowledge Server"}
```

---

# 十、测试 API

先设 token：
```bash
export TOKEN="你在.env里设置的token"
```

## 1）列出文档
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/documents
```

## 2）搜索
```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"员工请假制度","limit":5}'
```

`query` 按普通文本处理，多个空白分隔的关键词需要同时命中，空白查询返回空结果。
后端会转义 SQLite FTS5 查询语法，因此 `P5-35`、`P5.35` 和包含引号的文本可以直接查询；`AND`、`OR` 等按普通词处理。
全文检索仍使用 FTS5 的分词规则，标点通常是分隔符，因此 `P5-35` 也可能匹配 `P5 35`。
例如服务运行在 8016 端口时：

```bash
curl -X POST http://127.0.0.1:8016/api/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"P5-35","limit":5}'
```

修改搜索代码后需重启 Uvicorn，已有文档索引可以继续使用，无需重新运行 ingest。

## 3）查看全文
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/documents/1
```

## 4）重建索引
```bash
curl -X POST http://127.0.0.1:8000/api/reindex \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"full":false}'
```

---

# 十一、启动 MCP 服务

这个服务通常给 MCP client 使用。

```bash
cd /opt/mcp-knowledge
source .venv/bin/activate
python -m app.mcp_server
```

注意：
- 不同 `fastmcp` 版本支持的 transport 方式不同
- 如果你的客户端需要 stdio，本代码就能工作
- 如果你要远程 HTTP MCP，得看当前 SDK 版本支持情况

**我建议你生产环境中：**
- 对外主要暴露 **FastAPI HTTP**
- MCP 作为大模型客户端接入层

这是最稳的方案。

---

# 十二、配置 systemd

我们要让 HTTP 服务和 MCP 服务都能后台运行。

---

## 1）FastAPI 服务

创建：
```bash
sudo nano /etc/systemd/system/mcp-knowledge-api.service
```

内容：

```ini
[Unit]
Description=MCP Knowledge FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/mcp-knowledge
Environment="PATH=/opt/mcp-knowledge/.venv/bin"
ExecStart=/opt/mcp-knowledge/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

把 `User=ubuntu` 改成你的实际用户名。

启用：
```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-knowledge-api
sudo systemctl start mcp-knowledge-api
sudo systemctl status mcp-knowledge-api
```

查看日志：
```bash
journalctl -u mcp-knowledge-api -f
```

---

## 2）MCP 服务

创建：
```bash
sudo nano /etc/systemd/system/mcp-knowledge-mcp.service
```

内容：

```ini
[Unit]
Description=MCP Knowledge MCP Service
After=network.target mcp-knowledge-api.service
Requires=mcp-knowledge-api.service

[Service]
User=ubuntu
WorkingDirectory=/opt/mcp-knowledge
Environment="PATH=/opt/mcp-knowledge/.venv/bin"
ExecStart=/opt/mcp-knowledge/.venv/bin/python -m app.mcp_server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：
```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-knowledge-mcp
sudo systemctl start mcp-knowledge-mcp
sudo systemctl status mcp-knowledge-mcp
```

---

# 十三、配置 Nginx

## 1）创建 nginx 站点配置
```bash
sudo nano /etc/nginx/sites-available/mcp-knowledge
```

写入：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }
}
```

启用：
```bash
sudo ln -s /etc/nginx/sites-available/mcp-knowledge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

# 十四、启用 HTTPS

如果你有域名：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

完成后你就可以通过：
```bash
https://your-domain.com/health
```
访问。

---

# 十五、开放防火墙

如果你启用了 UFW：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

# 十六、自动增量索引

目前你已经有 `/api/reindex` 接口可以手工触发。

如果想自动执行，有两种常见办法：

---

## 方案A：Cron 定时扫描
每 5 分钟扫描一次

```bash
crontab -e
```

加入：
```cron
*/5 * * * * /opt/mcp-knowledge/scripts/reindex.sh >> /opt/mcp-knowledge/logs/reindex.log 2>&1
```

---

## 方案B：inotify 实时监听
更高级，但更复杂。  
从稳定性上讲，先用 cron 就够了。

---

# 十七、DOC / PDF 生产注意事项

## 1）老 DOC
`antiword` 能处理一部分，但不是百分百。
更稳做法：
- 统一批量转为 `.docx`

例如：
```bash
mkdir -p /opt/mcp-knowledge/raw/converted
libreoffice --headless --convert-to docx /opt/mcp-knowledge/raw/project/*.doc --outdir /opt/mcp-knowledge/raw/converted
```

## 2）扫描版 PDF
如果发现 PDF 提取为空，就说明很可能是扫描件。  
这时需要 OCR，后面可升级。

---

# 十八、MCP 客户端如何接

这部分取决于你的客户端。

## 如果你是自己写 AI 应用
最简单：
- 直接调用 `https://your-domain.com/api/search`
- 把返回的片段拼进 prompt
- 这是标准 RAG

## 如果你要给支持 MCP 的客户端
配置你的 MCP 进程即可。  
但要注意：
- 很多 MCP 客户端更偏好本地 stdio
- 远程 HTTP MCP 生态还在演进

所以实际生产里通常是：
- **主能力走 HTTP API**
- **MCP 作为工具层补充**

---

# 十九、生产级安全建议

你现在已经有 Token 了，但还建议再加 3 层：

## 1）Nginx Basic Auth（可选）
如果你怕 HTTP 接口被扫，可以额外加 Basic Auth。

## 2）IP 白名单（强烈推荐）
如果只有你自己的应用会访问，限制来源 IP 非常有效。

例如：
```nginx
location /api/ {
    allow 1.2.3.4;
    deny all;
    proxy_pass http://127.0.0.1:8000;
}
```

## 3）不要开放 uvicorn 端口到公网
只监听：
```bash
127.0.0.1:8000
```
然后由 Nginx 转发。

---

# 二十、建议加一个上传接口吗？

当前版本是：
- 你把文件直接上传到服务器 `raw/`
- 然后调用 `/api/reindex`

这已经适合很多内部场景。

如果你还想要：
- Web 上传文件
- 上传后自动索引

我也可以下一条给你补上 `/api/upload` 接口。

---

# 二十一、如何升级到 Qdrant 向量检索

等你当前系统稳定后，再升级。

## 1）部署 Qdrant
如果你服务器装了 Docker：

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v /opt/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

## 2）安装依赖
```bash
pip install qdrant-client sentence-transformers
```

## 3）增加 embedding 索引逻辑
流程变成：
- 切块
- 每个 chunk 生成向量
- 写入 Qdrant
- 查询时：
  - 向量检索 topK
  - 或 SQLite 关键词检索 + Qdrant 混合召回

---

# 二十二、为什么我建议你“先 SQLite，后 Qdrant”

因为生产系统第一优先级不是“最先进”，而是：

- 好部署
- 好排障
- 好恢复
- 结构清晰
- 先跑通业务

SQLite + HTTP API + MCP 已经足够支撑你当前“把资料给大模型访问”的核心需求。

---

# 二十三、建议你现在立刻执行的步骤

按顺序来：

## 1
创建项目目录、虚拟环境、requirements

## 2
复制我上面的所有代码文件

## 3
修改 `.env` 中的 Token

## 4
把资料放入 `/opt/mcp-knowledge/raw`

## 5
运行：
```bash
source /opt/mcp-knowledge/.venv/bin/activate
cd /opt/mcp-knowledge
python -m app.ingest
```

## 6
启动 API：
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 7
用 curl 测试 `/api/search`

## 8
配置 systemd

## 9
配置 nginx + HTTPS

---

# 二十四、我额外给你一个排障清单

## 看 API 日志
```bash
journalctl -u mcp-knowledge-api -f
```

## 看 MCP 日志
```bash
journalctl -u mcp-knowledge-mcp -f
```

## 测试数据库是否有内容
```bash
sqlite3 /opt/mcp-knowledge/data/knowledge.db
```

执行：
```sql
SELECT count(*) FROM documents;
SELECT count(*) FROM chunks;
.quit
```

## 测试接口是否需要 token
```bash
curl http://127.0.0.1:8000/api/documents
```
应该返回 401。

---

# 二十五、我对这套方案的建议结论

如果你问“现阶段最值得做的生产版本是什么”，我的答案就是：

> **FastAPI + SQLite FTS + Token 鉴权 + 增量索引 + MCP 包装 + Nginx HTTPS**

这是一个：
- 部署难度适中
- 成本低
- 非常稳定
- 可逐步升级
- 足够生产使用

的方案。

---

如果你愿意，我下一条可以继续直接给你两种增强版内容，任选其一：

### A. 我继续给你补：
**“文件上传接口 /api/upload + 自动触发索引”**

### B. 我继续给你补：
**“Qdrant 向量检索版完整升级代码”**

如果你想更完整，我建议先选 **A（上传接口）**，这样你的系统就更像一个完整知识库服务了。

