# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic==2.9.2", "typer==0.29.2", "PyMuPDF==1.24.10"]
# ///
# How to run: .venv/Scripts/python.exe -m evaluation.qa.run_manual attempt-1
from __future__ import annotations

import platform
import sys

from evaluation.qa import inventory_scenarios, score_scenarios
from evaluation.qa.support import ROOT, digest, save

sources = [*sorted((ROOT / 'evaluation').glob('*.py')), ROOT / 'app/search.py', ROOT / 'app/db.py', ROOT / 'app/config.py']
save('source-manifest-start.json', {str(path.relative_to(ROOT)): digest(path) for path in sources})
save('environment.json', {'python': sys.version, 'platform': platform.platform(), 'identity': '/root/f00_independent_qa'})
score_scenarios.run()
inventory_scenarios.run()
save('source-manifest-end.json', {str(path.relative_to(ROOT)): digest(path) for path in sources})
save('completed.json', {'score': 'PASS', 'inventory': 'PASS'})
print('Independent score and inventory scenarios PASS', flush=True)
