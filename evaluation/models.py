from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, NewType, Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

QueryId = NewType("QueryId", str)
ChunkId = NewType("ChunkId", int)
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PositiveId = Annotated[int, Field(strict=True, gt=0)]
Split = Literal["dev", "holdout"]
Category = Literal["parameter", "chinese", "table", "similar_model", "no_answer"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class EvaluationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __str__(self) -> str:
        return self.code


class Query(FrozenModel):
    query_id: Annotated[str, Field(min_length=1)]
    query: Annotated[str, Field(min_length=1)]
    category: Category
    split: Split
    origin: Literal["synthetic", "real"]
    corpus_id: Digest
    answerable: Annotated[bool | None, Field(strict=True)]
    relevant_chunk_ids: tuple[PositiveId, ...]
    label_status: Literal["complete", "partial", "unjudged"]

    @model_validator(mode="after")
    def consistent_label(self) -> Self:
        if not self.query.strip() or not self.query_id.strip():
            raise EvaluationError("blank_query_or_id")
        if len(set(self.relevant_chunk_ids)) != len(self.relevant_chunk_ids):
            raise EvaluationError("duplicate_relevant_id")
        match self.answerable:
            case True:
                if not self.relevant_chunk_ids or self.label_status == "unjudged":
                    raise EvaluationError("answerable_requires_judgments")
            case False:
                if self.relevant_chunk_ids or self.label_status != "complete":
                    raise EvaluationError("no_answer_requires_complete_empty_labels")
            case None:
                if self.relevant_chunk_ids or self.label_status != "unjudged":
                    raise EvaluationError("unknown_answer_requires_unjudged")
            case unreachable:
                assert_never(unreachable)
        return self


class Ranking(FrozenModel):
    query_id: str
    corpus_id: Digest
    query_set_sha256: Digest
    ranked_chunk_ids: tuple[PositiveId, ...]
    status: Literal["ok", "error"]
    error_kind: str | None = None

    @model_validator(mode="after")
    def consistent_status(self) -> Self:
        match self.status:
            case "ok":
                if self.error_kind is not None:
                    raise EvaluationError("successful_ranking_has_error")
            case "error":
                if self.ranked_chunk_ids or not self.error_kind:
                    raise EvaluationError("error_ranking_requires_empty_ids_and_kind")
            case unreachable:
                assert_never(unreachable)
        return self


@dataclass(frozen=True, slots=True)
class QuerySet:
    queries: tuple[Query, ...]
    sha256: str
    corpus_id: str

    def selected(self, split: Split) -> tuple[Query, ...]:
        selected = tuple(sorted((q for q in self.queries if q.split == split), key=lambda q: q.query_id))
        if not selected:
            raise EvaluationError("empty_selected_split")
        return selected


def load_queries(path: Path) -> QuerySet:
    """Parse once and hash the same bytes that supplied the judgments."""
    data = path.read_bytes()
    try:
        queries = tuple(Query.model_validate_json(line) for line in data.decode("utf-8").splitlines() if line.strip())
    except (ValidationError, UnicodeDecodeError) as error:
        raise EvaluationError("invalid_query_input") from error
    if not queries:
        raise EvaluationError("empty_query_set")
    if len({q.query_id for q in queries}) != len(queries):
        raise EvaluationError("duplicate_query_id")
    if len({q.corpus_id for q in queries}) != 1:
        raise EvaluationError("mixed_query_corpora")
    return QuerySet(queries, hashlib.sha256(data).hexdigest(), queries[0].corpus_id)


@dataclass(frozen=True, slots=True)
class RankingSet:
    rankings: tuple[Ranking, ...]
    sha256: str


def load_rankings(path: Path, dataset: QuerySet, split: Split) -> RankingSet:
    """Reject missing, stale, extra, duplicated, or differently scoped results."""
    data = path.read_bytes()
    try:
        rankings = tuple(Ranking.model_validate_json(line) for line in data.decode("utf-8").splitlines() if line.strip())
    except (ValidationError, UnicodeDecodeError) as error:
        raise EvaluationError("invalid_ranking_input") from error
    if any(r.corpus_id != dataset.corpus_id or r.query_set_sha256 != dataset.sha256 for r in rankings):
        raise EvaluationError("ranking_identity_mismatch")
    expected = {q.query_id for q in dataset.selected(split)}
    if len({r.query_id for r in rankings}) != len(rankings) or {r.query_id for r in rankings} != expected:
        raise EvaluationError("ranking_query_coverage_mismatch")
    return RankingSet(rankings, hashlib.sha256(data).hexdigest())
