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
