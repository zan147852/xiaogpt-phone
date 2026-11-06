#!/bin/bash
set -euo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates python3 python3-venv
python3 -m venv /root/xiaogpt-venv
/root/xiaogpt-venv/bin/python -m pip install --disable-pip-version-check -r /opt/xiaogpt/requirements.txt
/root/xiaogpt-venv/bin/python -m pip check
/root/xiaogpt-venv/bin/python - <<'PY'
import importlib.metadata
from xiaogpt.config import Config, HARDWARE_COMMAND_DICT
assert 'S12' in HARDWARE_COMMAND_DICT
Config(hardware='S12', tts='mi', stream=True, mute_xiaoai=True)
print('XiaoGPT', importlib.metadata.version('xiaogpt'), '— S12 适配检查通过')
PY
