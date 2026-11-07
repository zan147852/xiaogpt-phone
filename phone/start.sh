#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
task_dir=/data/data/com.termux/files/home/xiaogpt
export PATH=/data/data/com.termux/files/usr/bin:/system/bin
service_arguments="$task_dir/supervise.sh"
if [[ ${1:-} == --boot ]]; then
    service_arguments+=",--boot"
elif [[ $# -gt 0 ]]; then
    printf '用法：bash ~/xiaogpt/start.sh [--boot]\n' >&2
    exit 2
fi
if [[ $(cat "$task_dir/setup-status" 2>/dev/null) != configured_checks_passed ]]; then
    printf '请先完成配置与连接测试：bash ~/xiaogpt/open-configure.sh\n'
    exit 2
fi
exec 9>"$task_dir/service.lock"
if ! flock -n 9; then
    printf 'XiaoGPT 已在运行。\n'
    exit 0
fi
termux-wake-lock
am startservice --user 0 -n com.termux/com.termux.app.TermuxService \
    -a com.termux.service_execute \
    -d com.termux.file:/data/data/com.termux/files/usr/bin/bash \
    --esa com.termux.execute.arguments "$service_arguments" \
    --ez com.termux.execute.background true \
    --es com.termux.execute.cwd /data/data/com.termux/files/home > /dev/null
printf 'XiaoGPT 正在启动。停止：bash ~/xiaogpt/stop.sh\n'
