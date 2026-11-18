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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.app_port, log_level=settings.log_level)
