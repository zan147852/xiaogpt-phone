"""Apply public voice preferences without displaying private configuration."""
import json
import os
from pathlib import Path

from xiaogpt.config import Config
from voice_settings import VOICE_SETTINGS

os.umask(0o077)
private = Path('/root/.config/xiaogpt')
config_path = private / 'config.json'
original = config_path.read_text(encoding='utf-8')
settings = json.loads(original)
settings.update(VOICE_SETTINGS)
Config(**settings)
backup = private / 'config.before-voice-tuning.json'
if not backup.exists():
    backup.write_text(original, encoding='utf-8')
    backup.chmod(0o600)
temporary = private / 'config.json.new'
temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
temporary.chmod(0o600)
temporary.replace(config_path)
print('Voice tuning applied: streaming, conversational prompt, start/end chat commands.')
