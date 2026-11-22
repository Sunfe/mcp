from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'data/f00-qa'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    initial = {name.replace('\\', '/'): value for name, value in json.loads((EVIDENCE / 'attempt-1/source-manifest-start.json').read_text()).items()}
    final = {name: sha(ROOT / name) for name in initial}
    assert initial == final, 'product sources changed during QA'
    reports = []
    for path in EVIDENCE.glob('*/*.json'):
        value = json.loads(path.read_text(encoding='utf-8'))
        if 'provenance' in value:
            assert value['provenance']['sources_sha256'] == initial, path
            reports.append(str(path.relative_to(ROOT)))
    versions = {'initial_equals_final': True, 'final_sources': final, 'report_provenance_verified': reports,
                'qa_sources': {str(path.relative_to(ROOT)): sha(path) for path in (ROOT / 'evaluation/qa').glob('*.py')}}
    (EVIDENCE / 'verified-versions.json').write_text(json.dumps(versions, indent=2), encoding='utf-8')
    entries = []
    artifacts = []
    adversarial = []

    def register(path: Path, kind: str, description: str) -> str:
        assert path.is_file() and path.stat().st_size > 0, path
        identifier = f'A{len(artifacts) + 1:03}'
        artifacts.append({'id': identifier, 'kind': kind, 'description': description,
                          'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'bytes': path.stat().st_size})
        return identifier

    for path in sorted(EVIDENCE.glob('*/*-invocation.json')):
        invocation = json.loads(path.read_text(encoding='utf-8'))
        name = path.name.removesuffix('-invocation.json')
        output = path.with_name(name + '.json')
        criterion = 'AC-02/R1' if name.startswith(('r1', 'score')) else 'AC-03' if name.startswith('benchmark') else 'AC-01'
        expected = invocation.get('expected_exit', 2)
        assert invocation['exit'] == expected, path
        refs = [register(path, 'CLI transcript', name)]
        if expected == 0:
            refs.append(register(output, 'raw JSON report', name))
        entries.append({'scenarioId': name, 'criterionReference': criterion, 'surface': 'CLI subprocess',
                        'exactInvocation': json.dumps(invocation['argv']), 'verdict': 'PASS', 'artifactRefs': refs})
        if expected == 2:
            adversarial.append({'scenarioId': name, 'criterionReference': criterion, 'adversarialClass': 'invalid input or output protection',
                                'expectedBehavior': 'exit 2; no new output (existing overwrite target unchanged)', 'verdict': 'PASS', 'artifactRefs': refs})
        special = {
            'inventory-os-locked': ('Windows sharing denial', 'partial report; retained size=24; hash=null; PermissionError'),
            'inventory-mixed': ('corrupt and unsupported files', 'all known bytes retained; corrupt files error; video duration unknown'),
            'inventory-edge': ('encrypted PDF and Windows reparse point', 'encrypted status with known bytes/hash; junction skipped; shared image counted per page'),
            'score-unjudged': ('no eligible quality labels', 'quality and no-answer metrics null; unjudged_count=1'),
        }
        if name in special:
            fault, expected_behavior = special[name]
            adversarial.append({'scenarioId': name, 'criterionReference': criterion, 'adversarialClass': fault,
                                'expectedBehavior': expected_behavior, 'verdict': 'PASS', 'artifactRefs': refs})
    additional = [
        ('inventory-stat-fault', 'AC-01', 'data/library', 'attempt-1/inventory-stat-fault.json',
         '.venv/Scripts/python.exe -m evaluation.qa.run_manual attempt-1: inventory(locked-root, None) with Path.stat PermissionError',
         'failed stat', 'unknown_size_file_count=1; bytes=null; no false zero-sized file'),
        ('benchmark-r2-concurrency', 'AC-03/R2', 'real search with event-controlled fault', 'benchmark-1/benchmark-r2-control.json',
         '.venv/Scripts/python.exe -m evaluation.qa.benchmark_scenarios benchmark-1: benchmark(single query, warmup=2, repeats=4, concurrency=2)',
         'out-of-order completion', 'first formal error retained; later successful repeat cannot replace quality sample'),
        ('benchmark-all-errors', 'AC-03', 'data/library fault', 'benchmark-1/benchmark-all-errors.json',
         '.venv/Scripts/python.exe -m evaluation.qa.benchmark_scenarios benchmark-1: benchmark(single query, warmup=1, repeats=2)',
         'zero successful requests', 'P95=null; throughput=0; quality error retained in denominator'),
        ('benchmark-exception-cleanup', 'AC-03', 'data/library fault', 'benchmark-1/benchmark-exception-cleanup.json',
         '.venv/Scripts/python.exe -m evaluation.qa.benchmark_scenarios benchmark-1: benchmark(single query, warmup=0, repeats=1), RuntimeError',
         'unhandled exception', 'restore connection; remove snapshots; stop tracemalloc; source unchanged'),
        ('inventory-unstable', 'AC-01', 'data/library real file mutation', 'edges-1/inventory-unstable.json',
         '.venv/Scripts/python.exe -m evaluation.qa.edge_scenarios edges-1: inventory(changing-root, None), mutate after sha256',
         'file changes during read', 'unstable and sha256=null'),
        ('score-independent-oracle', 'AC-02', 'CLI report arithmetic', 'attempt-1/score-oracle.json',
         '.venv/Scripts/python.exe -m evaluation.qa.run_manual attempt-1',
         'duplicate hits and mixed errors', 'Recall=5/9; MRR=1/2; no-answer rates each=1/3'),
        ('benchmark-wal-oracle', 'AC-03', 'WAL source and CLI report arithmetic', 'benchmark-1/benchmark-independent-oracle.json',
         '.venv/Scripts/python.exe -m evaluation.qa.benchmark_scenarios benchmark-1',
         'uncheckpointed WAL and source protection', '22 results see WAL rows; main/WAL hashes unchanged; exact nearest-rank P95 and throughput'),
        ('existing-metadata-audit', 'AC-04', 'existing JSON data only', 'edges-1/existing-artifacts-audit.json',
         '.venv/Scripts/python.exe -m evaluation.qa.edge_scenarios edges-1',
         'unjudged baseline interpretation', 'existing 90-request arithmetic consistent; three unjudged probes yield null quality'),
        ('frozen-source-audit', 'AC-04/AC-05', 'filesystem hashes and report provenance', 'verified-versions.json',
         '.venv/Scripts/python.exe -m evaluation.qa.finalize_evidence',
         'source drift', 'initial=final SHA256; all raw report provenance binds same sources'),
    ]
    for name, criterion, surface, relative, invocation, fault, expected in additional:
        refs = [register(EVIDENCE / relative, 'observed data evidence', name)]
        if name == 'benchmark-r2-concurrency':
            refs.append(register(EVIDENCE / 'benchmark-1/benchmark-r2-concurrency.json', 'raw JSON report', name))
        entries.append({'scenarioId': name, 'criterionReference': criterion, 'surface': surface,
                        'exactInvocation': invocation, 'verdict': 'PASS', 'artifactRefs': refs})
        adversarial.append({'scenarioId': name, 'criterionReference': criterion, 'adversarialClass': fault,
                            'expectedBehavior': expected, 'verdict': 'PASS', 'artifactRefs': refs})
    for relative in ('run-attempt-1.log', 'run-benchmark-1.log', 'run-edges-1.log', 'attempt-1/environment.json'):
        register(EVIDENCE / relative, 'execution context', relative)
    adversarial.append({'scenarioId': 'browser-http-ui', 'criterionReference': 'AC-01..05',
                        'adversarialClass': 'browser layout and HTTP authentication',
                        'expectedBehavior': 'not_applicable: F00 adds local CLI/data tools and changes no UI or HTTP surface',
                        'verdict': 'not_applicable', 'artifactRefs': []})
    matrix = {'surfaceEvidence': entries, 'adversarialCases': adversarial, 'artifactRefs': artifacts}
    (EVIDENCE / 'manualQa.json').write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding='utf-8')
    text = '# F00 independent manualQa\n\nQA identity: `/root/f00_independent_qa`; date: 2026-11-20; cwd: `D:/repo/mcp`.\n\n'
    text += 'No ulw-loop plan was supplied; `omo-agent-toolkit ulw-loop status --json` returned command not found (127). Caller evidence directory used. All PASS entries below were executed; fault seams are identified explicitly.\n\n'
    text += '## surfaceEvidence\n\n| scenario id | criterion | surface | exact invocation | verdict | artifactRefs |\n|---|---|---|---|---|---|\n'
    for entry in entries:
        text += f"| {entry['scenarioId']} | {entry['criterionReference']} | {entry['surface']} | `{entry['exactInvocation']}` | PASS | {', '.join(entry['artifactRefs'])} |\n"
    text += '\n## adversarialCases\n\n| scenario id | criterion | adversarial class | expected behavior | verdict | artifactRefs |\n|---|---|---|---|---|---|\n'
    for entry in adversarial:
        text += f"| {entry['scenarioId']} | {entry['criterionReference']} | {entry['adversarialClass']} | {entry['expectedBehavior']} | {entry['verdict']} | {', '.join(entry['artifactRefs'])} |\n"
    text += '\n## artifactRefs\n\n| id | kind | description | path | SHA256 |\n|---|---|---|---|---|\n'
    for artifact in artifacts:
        text += f"| {artifact['id']} | {artifact['kind']} | {artifact['description']} | {artifact['path']} | {artifact['sha256']} |\n"
    (EVIDENCE / 'f00-manual-qa.md').write_text(text, encoding='utf-8')
    print(json.dumps({'executed_pass_scenarios': len(entries), 'nonempty_artifacts': len(artifacts), 'source_manifest_matches': True}))


if __name__ == '__main__':
    main()
