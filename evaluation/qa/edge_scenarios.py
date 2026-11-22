from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import fitz

import evaluation.inventory as inventory_module
from evaluation.qa.support import OUT, ROOT, cli, digest, jsonl, save


def run() -> None:
    raw = OUT / 'edge-files'
    raw.mkdir()
    with fitz.open() as pdf:
        pixels = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
        pixels.clear_with(130)
        image = pixels.tobytes('png')
        first = pdf.new_page()
        first.insert_text((50, 50), 'abcdefghijklmnopqrstuvxyz')
        xref = first.insert_image(fitz.Rect(50, 80, 100, 130), stream=image)
        pdf.new_page().insert_image(fitz.Rect(50, 80, 100, 130), xref=xref)
        pdf.save(raw / 'shared-image.pdf')
        pdf.save(raw / 'encrypted.pdf', encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='qa-owner', user_pw='qa-user')
    outside = OUT / 'outside-target'
    outside.mkdir()
    (outside / 'must-not-follow.txt').write_text('synthetic outside scan', encoding='utf-8')
    link = raw / 'junction'
    argv = ['cmd.exe', '/c', 'mklink', '/J', str(link), str(outside)]
    print('SURFACE Windows junction:', subprocess.list2cmdline(argv), flush=True)
    junction = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=10)
    save('junction-creation.json', {'argv': argv, 'exit': junction.returncode, 'stdout': junction.stdout, 'stderr': junction.stderr})
    assert junction.returncode == 0, junction.stderr
    report_path = cli('inventory-edge', ['inventory', '--root', str(raw)])
    report = json.loads(report_path.read_text())
    assert report['file_count'] == 2 and report['skipped_links'] == 1
    encrypted = next(row for row in report['files'] if row['status'] == 'encrypted')
    assert encrypted['bytes'] > 0 and encrypted['sha256'] and encrypted['pages'] is None
    image_pdf = next(row for row in report['files'] if row['pages'] == 2)
    assert image_pdf['image_reference_occurrences'] == 2
    assert image_pdf['pages_with_image_references'] == 2 and image_pdf['text_sparse_pages'] == 1
    before = digest(report_path)
    argv = [sys.executable, '-m', 'evaluation', 'inventory', '--root', str(raw), '--output', str(report_path)]
    print('SURFACE CLI overwrite:', subprocess.list2cmdline(argv), flush=True)
    overwrite = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
    assert overwrite.returncode == 2 and digest(report_path) == before
    save('overwrite-invocation.json', {'argv': argv, 'exit': overwrite.returncode, 'stderr': overwrite.stderr,
                                      'before_sha256': before, 'after_sha256': digest(report_path)})
    changing = OUT / 'changing-root'
    changing.mkdir()
    changed_file = changing / 'changing.txt'
    changed_file.write_text('before', encoding='utf-8')
    real_hash = inventory_module.sha256

    def mutate_after_hash(path: Path) -> str:
        value = real_hash(path)
        if path == changed_file:
            path.write_text('after modification', encoding='utf-8')
        return value

    print('SURFACE library: inventory(changing-root, None), file modification after hashing', flush=True)
    with patch.object(inventory_module, 'sha256', mutate_after_hash):
        changing_report = inventory_module.inventory(changing, None)
    assert changing_report.files[0].status == 'unstable' and changing_report.files[0].sha256 is None
    assert changing_report.status == 'partial'
    save('inventory-unstable.json', changing_report.model_dump(mode='json'))
    unjudged = {'query_id': 'u', 'query': 'synthetic unknown', 'category': 'table', 'split': 'dev',
                'origin': 'synthetic', 'corpus_id': '9' * 64, 'answerable': None,
                'relevant_chunk_ids': [], 'label_status': 'unjudged'}
    query_path = jsonl('unjudged.jsonl', [unjudged])
    ranks = jsonl('unjudged-ranks.jsonl', [{'query_id': 'u', 'corpus_id': '9' * 64,
        'query_set_sha256': digest(query_path), 'ranked_chunk_ids': [11], 'status': 'ok'}])
    output = cli('score-unjudged', ['score', '--queries', str(query_path), '--results', str(ranks)])
    summary = json.loads(output.read_text())['score']['summary']
    assert summary['recall_at_k'] is None and summary['mrr_at_k'] is None
    assert summary['empty_result_rate'] is None and summary['unjudged_count'] == 1
    cli('score-empty-split', ['score', '--queries', str(query_path), '--results', str(ranks), '--split', 'holdout'], 2)
    real_inventory = ROOT / 'data/f00-local/inventory-v2.json'
    real_baseline = ROOT / 'data/f00-local/manual-unjudged-v2.json'
    existing = json.loads(real_inventory.read_text(encoding='utf-8'))
    baseline = json.loads(real_baseline.read_text(encoding='utf-8'))
    assert existing['file_count'] == 1 and existing['total_bytes'] == 10406057
    assert existing['files'][0]['pages'] == 253
    perf = baseline['performance']
    latencies = sorted(row['latency_ms'] for row in baseline['requests'] if row['result']['status'] == 'ok')
    assert len(latencies) == 90 and perf['successful_p95_ms'] == latencies[85]
    assert perf['successful_queries_per_second'] == 90 / perf['elapsed_seconds']
    assert baseline['quality']['summary']['recall_at_k'] is None
    assert baseline['quality']['summary']['unjudged_count'] == 3
    save('existing-artifacts-audit.json', {'inventory_sha256': digest(real_inventory),
         'baseline_sha256': digest(real_baseline), 'p95_recomputed': latencies[85],
         'throughput_recomputed': 90 / perf['elapsed_seconds'], 'scope': 'existing metadata arithmetic; no original-file rerun', 'verdict': 'PASS'})
    save('completed.json', {'edges': 'PASS'})


if __name__ == '__main__':
    run()
    print('Independent edge scenarios PASS', flush=True)
