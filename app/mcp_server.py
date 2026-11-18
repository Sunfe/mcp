import httpx
from fastmcp import FastMCP
from app.config import settings

mcp = FastMCP("KnowledgeBaseMCP")

BASE_URL = f"http://{settings.app_host}:{settings.app_port}"
HEADERS = {"Authorization": f"Bearer {settings.api_token}"}


def request_api(method: str, path: str, *, timeout: float = 30, **kwargs) -> dict:
    try:
        # This API is on the same server; do not send its token through an HTTP proxy.
        with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=timeout, trust_env=False) as client:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (401, 403):
            raise RuntimeError("Knowledge API authentication failed. Check server-side API_TOKEN and restart the API and MCP session.") from None
        raise RuntimeError(f"Knowledge API returned HTTP {status} for {path}.") from None
    except httpx.RequestError:
        raise RuntimeError(
            f"Cannot reach knowledge API at {BASE_URL}. Check APP_HOST/APP_PORT in .env "
            "and start it with bash scripts/start_api.sh on the server."
        ) from None


@mcp.tool()
def list_documents() -> dict:
    """列出已索引的资料及其 document id、标题和分类。不了解资料库内容时先调用此工具。"""
    return request_api("GET", "/api/documents")


@mcp.tool()
def search_documents(query: str, limit: int = 5) -> dict:
    """搜索资料库中的文本片段。query 使用参数编号或简短关键词，例如 P5-35；
    空白分隔的多个关键词需要同时命中。返回标题、document_id、chunk_id、chunk_index 和内容。
    请基于命中片段回答并引用来源；没有结果时调整关键词，不要编造文档内容。
    """
    limit = max(1, min(limit, settings.max_search_limit))
    return request_api(
        "POST", "/api/search",
        json={"query": query, "limit": limit},
    )


@mcp.tool()
def get_document(document_id: int) -> dict:
    """按 list_documents 或 search_documents 返回的 document_id 获取全文和所有文本块。
    大文档响应可能很长，优先搜索具体关键词，仅在确实需要全文时调用。
    """
    return request_api("GET", f"/api/documents/{document_id}")


@mcp.tool()
def reindex_documents(full: bool = False) -> dict:
    """更新服务器文档索引，会写入数据库。仅在用户要求导入或重建时调用。
    full=True 会清空并重建已有索引；日常查询无需调用此工具。
    """
    return request_api(
        "POST", "/api/reindex",
        json={"full": full},
        timeout=300,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
