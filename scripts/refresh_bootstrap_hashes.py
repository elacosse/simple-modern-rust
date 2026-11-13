#!/usr/bin/env python3
"""Refresh bootstrap fingerprints after intentional template edits."""
import ast
import hashlib
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
script = root / 'bootstrap.py'
content = script.read_text(encoding='utf-8')
match = re.search(r'^EXPECTED = (.*)  # BOOTSTRAP_HASHES$', content, re.MULTILINE)
if not match:
    raise SystemExit('Could not find bootstrap fingerprints')
paths = ast.literal_eval(match.group(1))
fingerprints = {
    path: hashlib.sha256((root / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    for path in paths
}
script.write_text(content[:match.start(1)] + repr(fingerprints) + content[match.end(1):], encoding='utf-8')
print('Updated bootstrap fingerprints. Run make template-test before committing.')
