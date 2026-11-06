"""Reject common secrets and local artifacts before publishing a snapshot."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {'config.json', 'mi.token', 'pending-input.json', 'input-request.json'}
FORBIDDEN_SUFFIXES = {'.sqlite3', '.sqlite', '.db', '.apk', '.whl', '.mp3', '.zip', '.log', '.token'}
PATTERNS = [
    re.compile(r'\b(?:sk|ghp|gho)-?[A-Za-z0-9_]{24,}\b'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    re.compile(r'(?m)[\x22\x27](?:api_key|password|account)[\x22\x27]\s*:\s*[\x22\x27](?![\x22\x27]|YOUR_|unused|example|<)[^\x22\x27\r\n]{6,}[\x22\x27]'),
]


def main():
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=False)
    if result.returncode == 0 and result.stdout:
        paths = [ROOT / name for name in result.stdout.decode('utf-8').split('\0') if name]
    else:
        paths = [p for p in ROOT.rglob('*') if p.is_file() and not any(
            part in {'.git', '__pycache__', '.venv', 'check-state-cache'} or part.startswith('check-state-')
            for part in p.relative_to(ROOT).parts)]
    failures = []
    for path in paths:
        relative = path.relative_to(ROOT)
        if path.name in FORBIDDEN_NAMES or path.suffix in FORBIDDEN_SUFFIXES or path.stat().st_size > 1_000_000:
            failures.append(str(relative))
            continue
        content = path.read_text(encoding='utf-8')
        if any(pattern.search(content) for pattern in PATTERNS):
            failures.append(str(relative))
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)', content):
                if target.startswith(('https://', 'http://', '#', 'mailto:')):
                    continue
                destination = target.split('#', 1)[0]
                if destination and not (path.parent / destination).exists():
                    failures.append(str(relative) + ' -> broken documentation link')
    if failures:
        raise SystemExit('Review these files before publishing (values omitted): ' + ', '.join(failures))
    print(f'Publish check: {len(paths)} files; no common secret patterns or local binary artifacts found.')


if __name__ == '__main__':
    main()
