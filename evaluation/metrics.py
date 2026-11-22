from __future__ import annotations

from statistics import mean
from typing import assert_never

from evaluation.models import FrozenModel, Query, Ranking


class QueryMetric(FrozenModel):
    query_id: str
    category: str
    origin: str
    split: str
    label_status: str
    status: str
    answerable: bool | None
    relevant_count: int
    hit_count: int
    recall_at_k: float | None
    mrr_at_k: float | None
    returned_count: int


class Summary(FrozenModel):
    query_count: int
    answerable_count: int
    no_answer_count: int
    unjudged_count: int
    error_count: int
    partial_label_count: int
    recall_at_k: float | None
    mrr_at_k: float | None
    empty_result_rate: float | None
    false_positive_rate: float | None
    no_answer_error_rate: float | None
    quality_null_reason: str | None
    no_answer_null_reason: str | None


class Group(FrozenModel):
    dimension: str
    value: str
    summary: Summary


class Score(FrozenModel):
    k: int
    unit: str = "chunk"
    aggregation: str = "per_query_macro;partial_labels_are_restricted_recall"
    deduplication: str = "first_occurrence_then_top_k"
    summary: Summary
    groups: tuple[Group, ...]
    per_query: tuple[QueryMetric, ...]


def _per_query(query: Query, ranking: Ranking, k: int) -> QueryMetric:
    ids = tuple(dict.fromkeys(ranking.ranked_chunk_ids))[:k]
    relevant = set(query.relevant_chunk_ids)
    hits = relevant.intersection(ids)
    recall: float | None = None
    mrr: float | None = None
    match query.answerable:
        case True:
            recall = len(hits) / len(relevant)
            mrr = next((1 / rank for rank, chunk in enumerate(ids, 1) if chunk in relevant), 0.0)
        case False | None:
            pass
        case unreachable:
            assert_never(unreachable)
    return QueryMetric(query_id=query.query_id, category=query.category, origin=query.origin,
                       split=query.split, label_status=query.label_status, status=ranking.status,
                       answerable=query.answerable, relevant_count=len(relevant), hit_count=len(hits),
                       recall_at_k=recall, mrr_at_k=mrr, returned_count=len(ids))


def summarize(rows: tuple[QueryMetric, ...]) -> Summary:
    """Errors stay in labeled denominators; unjudged cases stay visible."""
    recalls = [r.recall_at_k for r in rows if r.recall_at_k is not None]
    mrrs = [r.mrr_at_k for r in rows if r.mrr_at_k is not None]
    absent = [r for r in rows if r.answerable is False]
    return Summary(
        query_count=len(rows), answerable_count=len(recalls), no_answer_count=len(absent),
        unjudged_count=sum(r.answerable is None for r in rows),
        error_count=sum(r.status == "error" for r in rows),
        partial_label_count=sum(r.label_status == "partial" for r in rows),
        recall_at_k=mean(recalls) if recalls else None,
        mrr_at_k=mean(mrrs) if mrrs else None,
        empty_result_rate=sum(r.status == "ok" and r.returned_count == 0 for r in absent) / len(absent) if absent else None,
        false_positive_rate=sum(r.status == "ok" and r.returned_count > 0 for r in absent) / len(absent) if absent else None,
        no_answer_error_rate=sum(r.status == "error" for r in absent) / len(absent) if absent else None,
        quality_null_reason=None if recalls else "no_eligible_queries",
        no_answer_null_reason=None if absent else "no_eligible_queries",
    )


def score(queries: tuple[Query, ...], rankings: tuple[Ranking, ...], k: int) -> Score:
    by_id = {ranking.query_id: ranking for ranking in rankings}
    rows = tuple(_per_query(q, by_id[q.query_id], k) for q in queries)
    groups = []
    for dimension in ("category", "origin", "split", "label_status"):
        values = {getattr(row, dimension) for row in rows}
        if dimension == "category":
            values.update(("parameter", "chinese", "table", "similar_model", "no_answer"))
        for value in sorted(values):
            subset = tuple(row for row in rows if getattr(row, dimension) == value)
            groups.append(Group(dimension=dimension, value=value, summary=summarize(subset)))
    return Score(k=k, summary=summarize(rows), groups=tuple(groups), per_query=rows)
