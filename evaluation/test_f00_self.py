from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.artifacts import PROJECT, sha256
from evaluation.benchmark import BenchmarkOptions, Request, benchmark, first_submissions
from evaluation.models import Ranking, load_queries, load_rankings
from evaluation.prepare_demo import prepare_demo


class F00SelfTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="f00-self-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.demo = self.root / "demo"
        prepare_demo(self.demo)
        self.dataset = load_queries(self.demo / "queries.jsonl")

    def invoke(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "evaluation", *arguments], cwd=PROJECT,
                              capture_output=True, text=True, timeout=30, check=False)

    def test_score_macro_deduplication_and_error_denominators(self) -> None:
        rankings = load_rankings(self.demo / "good.jsonl", self.dataset, "dev").rankings
        modified = tuple(r.model_copy(update={"ranked_chunk_ids": (999, 1, 1, 2)}) if r.query_id == "p"
                         else r.model_copy(update={"status": "error", "ranked_chunk_ids": (), "error_kind": "synthetic"}) if r.query_id == "n"
                         else r for r in rankings)
        result_path = self.root / "results.jsonl"
        result_path.write_text("\n".join(r.model_dump_json() for r in modified), encoding="utf-8")
        output = self.root / "score.json"

        result = self.invoke(["score", "--queries", str(self.demo / "queries.jsonl"), "--results", str(result_path),
                              "--k", "2", "--output", str(output)])

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))["score"]
        self.assertEqual(report["summary"]["recall_at_k"], 0.875)
        self.assertEqual(report["summary"]["mrr_at_k"], 0.875)
        self.assertEqual(report["summary"]["no_answer_error_rate"], 1)
        self.assertEqual(report["summary"]["empty_result_rate"], 0)
        self.assertEqual(report["summary"]["false_positive_rate"], 0)

    def test_score_rejects_corpus_changed_query_labels_and_missing_binding(self) -> None:
        rankings = load_rankings(self.demo / "good.jsonl", self.dataset, "dev").rankings
        cases = ("corpus", "query", "label", "missing")
        for variant in cases:
            with self.subTest(variant=variant):
                query_path = self.root / f"{variant}-queries.jsonl"
                rows = self.dataset.queries
                if variant == "query":
                    rows = tuple(q.model_copy(update={"query": "changed query"}) if q.query_id == "p" else q for q in rows)
                if variant == "label":
                    rows = tuple(q.model_copy(update={"relevant_chunk_ids": (5,)}) if q.query_id == "p" else q for q in rows)
                query_path.write_text("\n".join(q.model_dump_json() for q in rows) + "\n", encoding="utf-8")
                serialized = [r.model_dump() for r in rankings]
                if variant == "corpus":
                    for row in serialized:
                        row["corpus_id"] = "0" * 64
                if variant == "missing":
                    for row in serialized:
                        row.pop("query_set_sha256")
                result_path = self.root / f"{variant}-rankings.jsonl"
                result_path.write_text("\n".join(json.dumps(row) for row in serialized), encoding="utf-8")
                output = self.root / f"{variant}-output.json"

                result = self.invoke(["score", "--queries", str(query_path), "--results", str(result_path), "--output", str(output)])

                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())

    def test_inventory_keeps_bytes_for_readable_corrupt_files(self) -> None:
        raw = self.root / "raw"
        raw.mkdir()
        contents = {"broken.pdf": b"not a PDF, nonempty", "broken.docx": b"not a zip, nonempty", "other.bin": b"abcdef"}
        for name, content in contents.items():
            (raw / name).write_bytes(content)
        output = self.root / "inventory.json"

        result = self.invoke(["inventory", "--root", str(raw), "--output", str(output)])

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["total_bytes"], sum(map(len, contents.values())))
        self.assertEqual(sorted(item["status"] for item in report["files"]), ["error", "error", "unsupported"])
        self.assertTrue(all(item["sha256"] and item["bytes"] for item in report["files"]))
        self.assertEqual(report["status"], "partial")

    def test_inventory_distinguishes_empty_root_missing_root_and_overwrite(self) -> None:
        raw = self.root / "empty"
        raw.mkdir()
        output = self.root / "empty.json"

        completed = self.invoke(["inventory", "--root", str(raw), "--output", str(output)])
        overwrite = self.invoke(["inventory", "--root", str(raw), "--output", str(output)])
        absent = self.invoke(["inventory", "--root", str(raw / "absent"), "--output", str(self.root / "absent.json")])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["file_count"], 0)
        self.assertEqual(overwrite.returncode, 2)
        self.assertEqual(absent.returncode, 2)

    def test_benchmark_real_search_preserves_source_and_restores_connection(self) -> None:
        from app import search

        database = self.demo / "demo.db"
        original_hash = sha256(database)
        original_connection = search.get_conn

        result = benchmark(database, self.dataset, BenchmarkOptions(k=2, warmup=2, repeats=3, concurrency=2))

        self.assertEqual(sha256(database), original_hash)
        self.assertIs(search.get_conn, original_connection)
        self.assertEqual(result.performance.measured_requests, 15)
        self.assertEqual(result.performance.error_requests, 0)
        self.assertEqual(result.quality.summary.recall_at_k, 1)
        self.assertEqual(result.database.corpus_id, result.database_end_sha256)
        latencies = sorted(r.latency_ms for r in result.requests)
        self.assertEqual(result.performance.successful_p95_ms, latencies[14])
        self.assertEqual(result.performance.successful_queries_per_second, 15 / result.performance.elapsed_seconds)

    def test_first_submission_error_is_not_replaced_by_later_success(self) -> None:
        failed = Ranking(query_id="p", corpus_id=self.dataset.corpus_id, query_set_sha256=self.dataset.sha256,
                         status="error", error_kind="synthetic", ranked_chunk_ids=())
        successful = failed.model_copy(update={"status": "ok", "error_kind": None, "ranked_chunk_ids": (1, 2)})
        completion_order = (Request(submission_index=7, repeat_index=1, result=successful, latency_ms=1),
                            Request(submission_index=2, repeat_index=0, result=failed, latency_ms=20))

        chosen = first_submissions(completion_order)

        self.assertEqual(tuple(item.submission_index for item in chosen), (2,))
        self.assertEqual(chosen[0].result.status, "error")

    def test_unjudged_and_empty_groups_report_null_and_holdout_is_explicit(self) -> None:
        query = self.dataset.queries[0].model_copy(update={"answerable": None, "relevant_chunk_ids": (), "label_status": "unjudged"})
        query_path = self.root / "unjudged.jsonl"
        query_path.write_text(query.model_dump_json() + "\n", encoding="utf-8")
        data = load_queries(query_path)

        result = benchmark(self.demo / "demo.db", data, BenchmarkOptions(warmup=0, repeats=1))

        self.assertIsNone(result.quality.summary.recall_at_k)
        self.assertEqual(result.quality.summary.unjudged_count, 1)
        self.assertIsNone(result.quality.summary.empty_result_rate)
        group = next(g for g in result.quality.groups if g.dimension == "category" and g.value == "table")
        self.assertEqual(group.summary.query_count, 0)
        self.assertIsNone(group.summary.mrr_at_k)


if __name__ == "__main__":
    unittest.main()
