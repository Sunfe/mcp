from __future__ import annotations

import json

from evaluation.qa.support import Json, cli, digest, jsonl, save


def run() -> None:
    corpus = '3' * 64
    rows: list[dict[str, Json]] = []
    labels = ([11, 13, 17], [23], [29], [], [], [], [])
    for index, relevant in enumerate(labels):
        rows.append({'query_id': f'q{index}', 'query': f'independent query {index}', 'category': 'parameter',
                     'split': 'dev', 'origin': 'synthetic', 'corpus_id': corpus,
                     'answerable': None if index == 6 else index < 3,
                     'relevant_chunk_ids': relevant, 'label_status': 'unjudged' if index == 6 else 'complete'})
    rows.append({**rows[0], 'query_id': 'held', 'split': 'holdout'})
    query_path = jsonl('qa-queries.jsonl', rows)
    hits = ([97, 11, 11, 13, 17], [23], [], [], [41], [], [43])
    ranks = [{'query_id': f'q{index}', 'corpus_id': corpus, 'query_set_sha256': digest(query_path),
              'ranked_chunk_ids': ids, 'status': 'error' if index in (2, 5) else 'ok',
              'error_kind': 'OperationalError' if index in (2, 5) else None} for index, ids in enumerate(hits)]
    results_path = jsonl('qa-rankings.jsonl', ranks)
    args = ['score', '--queries', str(query_path), '--results', str(results_path), '--k', '3']
    report = json.loads(cli('score-hand-oracle', args).read_text(encoding='utf-8'))['score']
    summary = report['summary']
    assert abs(summary['recall_at_k'] - 5 / 9) < 1e-12
    assert summary['mrr_at_k'] == 0.5
    assert summary['error_count'] == 2 and summary['unjudged_count'] == 1
    assert all(summary[key] == 1 / 3 for key in ('empty_result_rate', 'false_positive_rate', 'no_answer_error_rate'))
    empty = next(group['summary'] for group in report['groups'] if group['value'] == 'table')
    assert empty['query_count'] == 0 and empty['recall_at_k'] is None
    save('score-oracle.json', {'expected_recall': '((2/3)+1+0)/3=5/9', 'expected_mrr': '(1/2+1+0)/3=1/2',
                              'no_answer_each': '1/3', 'observed': summary, 'verdict': 'PASS'})
    bad = [{**rank, 'ranked_chunk_ids': []} for rank in ranks]
    bad_path = jsonl('qa-all-miss.jsonl', bad)
    report_bad = json.loads(cli('score-all-miss', ['score', '--queries', str(query_path), '--results', str(bad_path)]).read_text())
    assert report_bad['score']['summary']['recall_at_k'] == report_bad['score']['summary']['mrr_at_k'] == 0
    cases = {
        'corpus': [{**rank, 'corpus_id': '4' * 64} for rank in ranks],
        'hash': [{**rank, 'query_set_sha256': '5' * 64} for rank in ranks],
        'missing-binding': [{key: value for key, value in rank.items() if key != 'query_set_sha256'} for rank in ranks],
        'duplicate': [*ranks, ranks[0]], 'missing-row': ranks[:-1],
        'extra-row': [*ranks, {**ranks[0], 'query_id': 'unknown'}],
    }
    for name, invalid in cases.items():
        path = jsonl('r1-' + name + '.jsonl', invalid)
        cli('r1-' + name, ['score', '--queries', str(query_path), '--results', str(path)], 2)
    changes = {'query': {**rows[0], 'query': 'changed text'}, 'label': {**rows[0], 'relevant_chunk_ids': [31]},
               'holdout': {**rows[-1], 'query': 'changed held-out text'}}
    for name, changed in changes.items():
        replacement = [*rows[:-1], changed] if name == 'holdout' else [changed, *rows[1:]]
        path = jsonl('changed-' + name + '.jsonl', replacement)
        cli('r1-changed-' + name, ['score', '--queries', str(path), '--results', str(results_path)], 2)
    empty_path = jsonl('empty-queries.jsonl', [])
    cli('score-empty-dataset', ['score', '--queries', str(empty_path), '--results', str(results_path)], 2)
    cli('score-invalid-k', [*args[:-1], '0'], 2)
    held_rank = jsonl('held-rank.jsonl', [{**ranks[0], 'query_id': 'held'}])
    held_report = json.loads(cli('score-explicit-holdout', ['score', '--queries', str(query_path), '--results', str(held_rank), '--split', 'holdout']).read_text())
    assert held_report['score']['summary']['query_count'] == 1
    assert held_report['score']['summary']['recall_at_k'] == 1
