#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot invokes this after Android permits boot tasks (normally after unlock).
set -euo pipefail
umask 077
task_dir=/data/data/com.termux/files/home/xiaogpt
export PATH=/data/data/com.termux/files/usr/bin:/system/bin
date +%s > "$task_dir/last-boot-time"
printf 'dispatched\n' > "$task_dir/boot-status"
exec bash "$task_dir/start.sh" --boot
