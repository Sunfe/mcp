from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


class ReindexRequest(BaseModel):
    full: Optional[bool] = False
