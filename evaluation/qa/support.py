from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Final, TypeAlias

ROOT: Final = Path(__file__).resolve().parents[2]
OUT: Final = ROOT / 'data' / 'f00-qa' / sys.argv[1]
OUT.mkdir(parents=True, exist_ok=False)
Json: TypeAlias = None | bool | int | float | str | list['Json'] | dict[str, 'Json']


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name: str, value: Json) -> Path:
    target = OUT / name
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return target


def jsonl(name: str, rows: list[dict[str, Json]]) -> Path:
    target = OUT / name
    target.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    return target


def cli(name: str, arguments: list[str], expected: int = 0) -> Path:
    output = OUT / (name + '.json')
    argv = [sys.executable, '-m', 'evaluation', *arguments, '--output', str(output)]
    print('SURFACE CLI:', subprocess.list2cmdline(argv), flush=True)
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30, check=False)
    save(name + '-invocation.json', {'argv': argv, 'cwd': str(ROOT), 'exit': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr, 'expected_exit': expected})
    assert result.returncode == expected, (name, result.returncode, result.stderr)
    if expected:
        assert not output.exists(), name
    return output
