#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
task_dir=/data/data/com.termux/files/home/xiaogpt
export PATH=/data/data/com.termux/files/usr/bin:/system/bin
if [[ -r "$task_dir/supervisor.pid" ]]; then
    read -r service_pid < "$task_dir/supervisor.pid"
    if [[ $service_pid =~ ^[0-9]+$ ]] && [[ -r /proc/$service_pid/cmdline ]] && \
        tr '\0' ' ' < "/proc/$service_pid/cmdline" | grep -Fq "$task_dir/supervise.sh"; then
        kill -TERM "$service_pid" || true
    fi
fi
proot-distro kill xiaogpt >/dev/null 2>&1 || true
printf 'stopped\n' > "$task_dir/service-status"
termux-wake-unlock
printf 'XiaoGPT 已停止。启动：bash ~/xiaogpt/start.sh\n'
