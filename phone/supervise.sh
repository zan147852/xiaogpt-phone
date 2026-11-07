#!/data/data/com.termux/files/usr/bin/bash
set -uo pipefail
umask 077
task_dir=/data/data/com.termux/files/home/xiaogpt
export PATH=/data/data/com.termux/files/usr/bin:/system/bin
exec 9>"$task_dir/service.lock"
flock -w 5 9 || exit 0
printf '%s\n' "$BASHPID" > "$task_dir/supervisor.pid"
network_pid=''
cleanup() {
    if [[ -n "$network_pid" ]]; then
        kill -TERM "$network_pid" 2>/dev/null || true
        wait "$network_pid" 2>/dev/null || true
    fi
    printf 'stopped\n' > "$task_dir/service-status"
    exit 0
}
trap cleanup TERM INT
if [[ ${1:-} == --boot ]]; then
    printf 'waiting_for_network\n' > "$task_dir/service-status"
    printf 'waiting_for_network\n' > "$task_dir/boot-status"
    python "$task_dir/wait_network.py" --timeout 600 > /dev/null 2>&1 &
    network_pid=$!
    wait "$network_pid"
    network_result=$?
    network_pid=''
    if [[ $network_result != 0 ]]; then
        printf 'boot_network_timeout\n' > "$task_dir/service-status"
        printf 'network_timeout\n' > "$task_dir/boot-status"
        termux-wake-unlock
        exit "$network_result"
    fi
    printf 'network_ready\n' > "$task_dir/boot-status"
fi
for attempt in 1 2 3; do
    printf 'starting\n' > "$task_dir/service-status"
    proot-distro login --bind "$task_dir:/opt/xiaogpt" xiaogpt -- \
        /root/xiaogpt-venv/bin/python /opt/xiaogpt/run.py > /dev/null 2>&1
    result=$?
    if [[ $result == 2 ]]; then
        printf 'configuration_required\n' > "$task_dir/service-status"
        exit 2
    fi
    if [[ $result == 0 ]]; then
        printf 'stopped\n' > "$task_dir/service-status"
        exit 0
    fi
    if [[ $attempt -lt 3 ]]; then
        printf 'waiting_to_retry\n' > "$task_dir/service-status"
        sleep 30
    fi
done
printf 'needs_attention\n' > "$task_dir/service-status"
