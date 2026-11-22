from __future__ import annotations

import json
import sqlite3
import threading
import tracemalloc
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import search
from evaluation.benchmark import BenchmarkOptions, benchmark
from evaluation.models import load_queries
from evaluation.qa.support import OUT, ROOT, cli, digest, jsonl, save


def run() -> None:
    database = OUT / 'independent-wal.db'
    with closing(sqlite3.connect(database)) as owner:
        owner.execute('PRAGMA journal_mode=WAL')
        owner.execute('PRAGMA wal_autocheckpoint=0')
        owner.executescript('''CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT, category TEXT);
            CREATE TABLE chunks(id INTEGER PRIMARY KEY, document_id INTEGER, chunk_index INTEGER, content TEXT);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(content, chunk_id UNINDEXED, document_id UNINDEXED);
            INSERT INTO documents VALUES(7, 'QA synthetic', 'qa');''')
        for identifier, content in ((11, 'quartz motor 91'), (23, 'cobalt voltage 37')):
            owner.execute('INSERT INTO chunks VALUES(?,7,0,?)', (identifier, content))
            owner.execute('INSERT INTO chunks_fts VALUES(?,?,7)', (content, identifier))
        owner.commit()
        copied = OUT / 'independent-reference-backup.db'
        with closing(sqlite3.connect(copied)) as reference:
            owner.backup(reference)
        corpus = digest(copied)
        query_path = jsonl('benchmark-queries.jsonl', [
            {'query_id': identifier, 'query': query, 'category': 'parameter', 'split': 'dev',
             'origin': 'synthetic', 'corpus_id': corpus, 'answerable': True,
             'relevant_chunk_ids': [chunk], 'label_status': 'complete'}
            for identifier, query, chunk in (('a', 'quartz', 11), ('b', 'cobalt', 23))])
        sources = (database, database.with_suffix('.db-wal'))
        before = {path.name: digest(path) for path in sources}
        report_path = cli('benchmark-concurrent', ['benchmark', '--database', str(database), '--queries', str(query_path),
                            '--k', '2', '--warmup', '3', '--repeats', '11', '--concurrency', '2'])
        report = json.loads(report_path.read_text())
        latencies = sorted(row['latency_ms'] for row in report['requests'])
        perf = report['performance']
        assert perf['measured_requests'] == perf['successful_requests'] == 22
        assert perf['error_requests'] == 0 and perf['warmup_requests'] == 3
        assert perf['successful_p95_ms'] == latencies[20]
        assert perf['successful_queries_per_second'] == 22 / perf['elapsed_seconds']
        assert report['quality']['summary']['recall_at_k'] == report['quality']['summary']['mrr_at_k'] == 1
        assert report['database']['chunks'] == report['database']['fts_rows'] == 2
        assert report['database']['corpus_id'] == report['database_end_sha256'] == corpus
        assert before == {path.name: digest(path) for path in sources}
        assert perf['python_allocated_peak_bytes'] > 0 and perf['process_peak']['bytes'] > 0
        save('benchmark-independent-oracle.json', {'source_before_after': before, 'wal_bytes': sources[1].stat().st_size,
            'nearest_rank': 21, 'p95_recomputed': latencies[20], 'throughput_recomputed': 22 / perf['elapsed_seconds'],
            'process_peak': perf['process_peak'], 'verdict': 'PASS'})
        rows = json.loads(query_path.read_text().splitlines()[0])
        one_path = jsonl('single-query.jsonl', [rows])
        dataset = load_queries(one_path)
        original_search = search.search_documents
        original_connection = search.get_conn
        completed_later = threading.Event()
        lock = threading.Lock()
        sequence: list[int] = []
        completion: list[int] = []
        snapshot_paths: set[Path] = set()
        readonly_denials: list[str] = []

        def controlled_search(query: str, limit: int = 5):
            with lock:
                call = len(sequence)
                sequence.append(call)
            with closing(search.get_conn()) as conn:
                snapshot_paths.add(Path(conn.execute('PRAGMA database_list').fetchone()[2]))
                try:
                    conn.execute("INSERT INTO documents VALUES(999,'forbidden','qa')")
                except sqlite3.OperationalError as error:
                    readonly_denials.append(str(error))
                else:
                    raise AssertionError('snapshot accepted write')
            if call == 0:
                raise sqlite3.OperationalError('warmup fault')
            if call == 2:
                assert completed_later.wait(10), 'later formal request did not complete'
                completion.append(call)
                raise sqlite3.OperationalError('first formal fault')
            result = original_search(query, limit)
            completion.append(call)
            if call == 3:
                completed_later.set()
            return result

        print('SURFACE library: benchmark(single query, warmup=2, repeats=4, concurrency=2); event-controlled real search fault', flush=True)
        with patch.object(search, 'search_documents', controlled_search):
            adversarial = benchmark(database, dataset, BenchmarkOptions(k=2, warmup=2, repeats=4, concurrency=2))
        save('benchmark-r2-concurrency.json', adversarial.model_dump(mode='json'))
        assert completion.index(3) < completion.index(2)
        assert adversarial.quality_submission_indices == {'a': 0}
        assert adversarial.first_results[0].status == 'error'
        assert adversarial.quality.summary.recall_at_k == adversarial.quality.summary.mrr_at_k == 0
        assert adversarial.performance.warmup_errors == 1
        assert adversarial.performance.successful_requests == 3 and adversarial.performance.error_requests == 1
        assert [request.repeat_index for request in adversarial.requests] == [0, 1, 2, 3]
        assert adversarial.repeat_rankings_stable == {'a': False}
        assert search.get_conn is original_connection
        assert all(not path.exists() for path in snapshot_paths)
        assert len(readonly_denials) == 6
        save('benchmark-r2-control.json', {'call_sequence': sequence, 'completion_order': completion,
            'snapshot_paths_cleaned': [str(path) for path in snapshot_paths], 'readonly_denials': readonly_denials,
            'connection_restored': True, 'verdict': 'PASS'})

        def failing_search(query: str, limit: int = 5):
            raise sqlite3.OperationalError('all requests fail')

        print('SURFACE library: benchmark(single query, warmup=1, repeats=2), all SQLite errors', flush=True)
        with patch.object(search, 'search_documents', failing_search):
            failed = benchmark(database, dataset, BenchmarkOptions(warmup=1, repeats=2))
        assert failed.performance.successful_p95_ms is None
        assert failed.performance.successful_queries_per_second == 0
        assert failed.performance.error_requests == 2 and failed.quality.summary.recall_at_k == 0
        save('benchmark-all-errors.json', failed.model_dump(mode='json'))

        def fatal_search(query: str, limit: int = 5):
            with closing(search.get_conn()) as conn:
                snapshot_paths.add(Path(conn.execute('PRAGMA database_list').fetchone()[2]))
            raise RuntimeError('independent unhandled fault')

        print('SURFACE library: benchmark(single query, warmup=0), unhandled RuntimeError cleanup', flush=True)
        with patch.object(search, 'search_documents', fatal_search):
            try:
                benchmark(database, dataset, BenchmarkOptions(warmup=0, repeats=1))
            except RuntimeError as error:
                assert str(error) == 'independent unhandled fault'
            else:
                raise AssertionError('fatal fault unexpectedly swallowed')
        assert search.get_conn is original_connection and not tracemalloc.is_tracing()
        assert all(not path.exists() for path in snapshot_paths)
        assert before == {path.name: digest(path) for path in sources}
        save('benchmark-exception-cleanup.json', {'source_before_after': before, 'connection_restored': True,
            'tracemalloc_stopped': True, 'snapshot_paths_cleaned': [str(path) for path in snapshot_paths], 'verdict': 'PASS'})
        invalid_path = jsonl('wrong-corpus.jsonl', [{**rows, 'corpus_id': '8' * 64}])
        cli('benchmark-wrong-corpus', ['benchmark', '--database', str(database), '--queries', str(invalid_path)], 2)
        invalid_label = jsonl('missing-chunk.jsonl', [{**rows, 'relevant_chunk_ids': [9999]}])
        cli('benchmark-missing-chunk', ['benchmark', '--database', str(database), '--queries', str(invalid_label)], 2)
    save('completed.json', {'benchmark': 'PASS'})


if __name__ == '__main__':
    save('source-manifest-start.json', {str(path.relative_to(ROOT)): digest(path) for path in (ROOT / 'evaluation').glob('*.py')})
    run()
    print('Independent benchmark scenarios PASS', flush=True)
