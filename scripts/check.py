"""Run offline regression checks; add --full when XiaoGPT is installed."""
import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Include XiaoGPT integration checks.')
    args = parser.parse_args()
    for path in [*ROOT.glob('app/*.py'), *ROOT.glob('tests/*.py'), *ROOT.glob('scripts/*.py')]:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tests = ['check-memory-local.py', 'check-memory-integration-local.py', 'speech-check.py', 'network-check.py']
    if args.full:
        tests += ['memory-check.py', 'conversation-check.py', 'runtime-check.py', 'assisted-input-check.py']
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'app') + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONIOENCODING'] = 'utf-8'
    for name in tests:
        subprocess.run([sys.executable, str(ROOT / 'tests' / name)], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'release-check.py')], cwd=ROOT, check=True)
    print('All selected offline checks passed. No model or Xiaomi requests were sent.')


if __name__ == '__main__':
    main()
