#!/usr/bin/env python3
"""Exercise generation in a disposable copy, including failure paths."""
from pathlib import Path
from datetime import date
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ARGS = ['--name', 'hello-world', '--owner', 'example-owner', '--author', 'Ada "A" Lovelace', '--email', 'ada@example.org', '--description', 'A "quoted" greeting']


def run(args, cwd, success=True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if (result.returncode == 0) != success:
        raise RuntimeError(f'{args}:\n{result.stdout}\n{result.stderr}')
    return result


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file() and 'target' not in p.parts}


with tempfile.TemporaryDirectory(prefix='template-test-') as temp:
    project = Path(temp) / 'project'
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns('.git', 'target', '__pycache__'))
    before = snapshot(project)
    for name in ('../bad', 'std', 'core', 'clap', 'con', 'com1', 'a' * 65):
        run(['python3', 'bootstrap.py', *ARGS[:1], name, *ARGS[2:]], project, False)
        assert before == snapshot(project), f'invalid name {name} changed the project'
    temp_file = project / 'Cargo.toml.bootstrap-tmp'
    temp_file.write_text('existing user data')
    run(['python3', 'bootstrap.py', *ARGS], project, False)
    assert temp_file.read_text() == 'existing user data'
    temp_file.unlink()
    assert before == snapshot(project), 'temporary-file failure changed the project'
    (project / 'src/main.rs').write_text('modified')
    modified = snapshot(project)
    run(['python3', 'bootstrap.py', *ARGS], project, False)
    assert modified == snapshot(project), 'marker failure changed the project'
    (project / 'src/main.rs').write_bytes(before['src/main.rs'])
    manifest = project / 'Cargo.toml'
    manifest.write_bytes(manifest.read_bytes().replace(b'\n', b'\r\n'))
    run(['python3', 'bootstrap.py', *ARGS], project)
    assert not (project / 'bootstrap.py').exists()
    assert not (project / '.github/workflows/template.yml').exists()
    assert not (project / 'scripts/refresh_bootstrap_hashes.py').exists()
    assert f'Copyright (c) {date.today().year} Ada' in (project / 'LICENSE').read_text()
    assert 'hello_world' in (project / 'src/main.rs').read_text()
    assert 'A \\"quoted\\" greeting' in (project / 'Cargo.toml').read_text()
    run(['make', 'check'], project)
    run(['make', 'build'], project)
    listing = run(['cargo', 'package', '--list', '--locked', '--allow-dirty'], project).stdout
    assert 'src/main.rs' in listing and 'Cargo.lock' in listing
    result = run(['cargo', 'run', '--locked', '--', 'Ada'], project)
    assert result.stdout.strip() == 'Hello, Ada!'
    print('Generated project and failure paths passed.')
