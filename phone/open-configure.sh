#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
task_dir=/data/data/com.termux/files/home/xiaogpt
export PATH=/data/data/com.termux/files/usr/bin:/system/bin
termux-wake-lock
proot-distro login --bind "$task_dir:/opt/xiaogpt" xiaogpt -- \
    /root/xiaogpt-venv/bin/python /opt/xiaogpt/configure.py "$@"
if [[ $(cat "$task_dir/setup-status") == configured_checks_passed ]]; then
    bash "$task_dir/start.sh"
fi
