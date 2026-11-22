from __future__ import annotations

import sqlite3
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from math import ceil
from pathlib import Path
from time import perf_counter_ns
from typing import Annotated
from unittest.mock import patch

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError

from evaluation.artifacts import Provenance, provenance
from evaluation.database import DatabaseSnapshot, describe_database, readonly_connection, snapshot_database
from evaluation.metrics import Score, score
from evaluation.models import EvaluationError, FrozenModel, Query, QuerySet, Ranking, Split
from evaluation.resources import ProcessPeak, process_peak


class BenchmarkOptions(FrozenModel):
    split: Split = "dev"
    k: Annotated[int, Field(gt=0)] = 5
    warmup: Annotated[int, Field(ge=0)] = 5
    repeats: Annotated[int, Field(gt=0)] = 10
    concurrency: Annotated[int, Field(gt=0)] = 1


class SearchHit(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    chunk_id: Annotated[int, Field(strict=True, gt=0)]


class Request(FrozenModel):
    submission_index: int
    repeat_index: int
    result: Ranking
    latency_ms: float


class Performance(FrozenModel):
    measured_requests: int
    successful_requests: int
    error_requests: int
    error_rate: float
    warmup_requests: int
    warmup_errors: int
    elapsed_seconds: float
    successful_queries_per_second: float
    successful_p95_ms: float | None
    p95_method: str = "nearest_rank_ceil_0.95N_successes_only"
    throughput_window: str = "before_first_submit_until_all_complete;includes_queueing"
    latency_window: str = "function_call_only;excludes_executor_queue"
    request_timeout: str = "not_enforced"
    python_allocated_peak_bytes: int
    process_peak: ProcessPeak


class Benchmark(FrozenModel):
    kind: str = "benchmark"
    provenance: Provenance
    source: str = "app.search.search_documents_on_readonly_snapshot;not_API_or_MCP"
    options: BenchmarkOptions
    database: DatabaseSnapshot
    database_end_sha256: str
    query_set_sha256: str
    performance: Performance
    requests: tuple[Request, ...]
    first_results: tuple[Ranking, ...]
    quality_submission_indices: dict[str, int]
    repeat_rankings_stable: dict[str, bool]
    quality: Score


def first_submissions(requests: tuple[Request, ...]) -> tuple[Request, ...]:
    selected: dict[str, Request] = {}
    for request in sorted(requests, key=lambda item: item.submission_index):
        selected.setdefault(request.result.query_id, request)
    return tuple(selected.values())


def _execute_query(query: Query, indices: tuple[int, int], binding: tuple[QuerySet, int]) -> Request:
    from app.search import search_documents

    dataset, limit = binding
    started = perf_counter_ns()
    try:
        try:
            raw_rows = search_documents(query.query, limit=limit)
        finally:
            latency_ms = (perf_counter_ns() - started) / 1_000_000
        hits = TypeAdapter(tuple[SearchHit, ...]).validate_python(raw_rows)
        result = Ranking(query_id=query.query_id, corpus_id=dataset.corpus_id, query_set_sha256=dataset.sha256,
                         ranked_chunk_ids=tuple(hit.chunk_id for hit in hits), status="ok")
    except (sqlite3.Error, OSError, ValidationError) as error:
        result = Ranking(query_id=query.query_id, corpus_id=dataset.corpus_id, query_set_sha256=dataset.sha256,
                         ranked_chunk_ids=(), status="error", error_kind=type(error).__name__)
    return Request(submission_index=indices[0], repeat_index=indices[1], result=result,
                   latency_ms=latency_ms)


def benchmark(database: Path, dataset: QuerySet, options: BenchmarkOptions) -> Benchmark:
    from app import search as production_search
    from evaluation.artifacts import sha256

    queries = dataset.selected(options.split)
    with snapshot_database(database) as copied:
        description = describe_database(copied)
        if description.corpus_id != dataset.corpus_id:
            raise EvaluationError("benchmark_corpus_mismatch")
        with closing(readonly_connection(copied)) as conn:
            actual = {int(row[0]) for row in conn.execute("SELECT id FROM chunks")}
        if any(chunk not in actual for q in queries for chunk in q.relevant_chunk_ids):
            raise EvaluationError("relevant_chunk_missing_from_snapshot")

        def connection() -> sqlite3.Connection:
            return readonly_connection(copied)

        def execute(job: tuple[int, Query]) -> Request:
            index, query = job
            return _execute_query(query, (index, index // len(queries)), (dataset, options.k))

        with patch.object(production_search, "get_conn", connection):
            warmup = tuple(execute((index, queries[index % len(queries)])) for index in range(options.warmup))
            jobs = tuple(enumerate(queries * options.repeats))
            tracemalloc.start()
            try:
                started = perf_counter_ns()
                with ThreadPoolExecutor(max_workers=options.concurrency) as pool:
                    requests = tuple(pool.map(execute, jobs))
                elapsed = (perf_counter_ns() - started) / 1_000_000_000
                _current, allocated_peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        end_hash = sha256(copied)
        if end_hash != description.corpus_id:
            raise EvaluationError("snapshot_changed_during_benchmark")
    first = first_submissions(requests)
    successes = sorted(r.latency_ms for r in requests if r.result.status == "ok")
    errors = len(requests) - len(successes)
    performance = Performance(measured_requests=len(requests), successful_requests=len(successes), error_requests=errors,
        error_rate=errors / len(requests), warmup_requests=len(warmup), warmup_errors=sum(r.result.status == "error" for r in warmup),
        elapsed_seconds=elapsed, successful_queries_per_second=len(successes) / elapsed,
        successful_p95_ms=successes[ceil(0.95 * len(successes)) - 1] if successes else None,
        python_allocated_peak_bytes=allocated_peak, process_peak=process_peak())
    return Benchmark(provenance=provenance(), options=options, database=description, database_end_sha256=end_hash,
        query_set_sha256=dataset.sha256, performance=performance, requests=requests,
        first_results=tuple(r.result for r in first), quality_submission_indices={r.result.query_id: r.submission_index for r in first},
        repeat_rankings_stable={q.query_id: len({(r.result.status, r.result.ranked_chunk_ids) for r in requests if r.result.query_id == q.query_id}) == 1 for q in queries},
        quality=score(queries, tuple(r.result for r in first), options.k))
