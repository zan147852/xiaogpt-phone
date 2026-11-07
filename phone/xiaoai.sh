#!/data/data/com.termux/files/usr/bin/bash
# One discoverable entry point for daily phone operations.
set -euo pipefail
task_dir=/data/data/com.termux/files/home/xiaogpt

run_python() {
    proot-distro login --bind "$task_dir:/opt/xiaogpt" xiaogpt -- \
        /root/xiaogpt-venv/bin/python "/opt/xiaogpt/$1" "${@:2}"
}

show_status() {
    printf '配置：'; cat "$task_dir/setup-status" 2>/dev/null || printf '尚未安装\n'
    printf '状态：'; cat "$task_dir/service-status" 2>/dev/null || printf '尚未启动\n'
    printf '完成回答：'; cat "$task_dir/completed-answers" 2>/dev/null || printf '0\n'
    if [[ -f "$task_dir/service.lock" ]]; then
        if (flock -n 9) 9>"$task_dir/service.lock"; then
            printf '进程锁：未占用（服务未运行）\n'
        else
            printf '进程锁：占用中\n'
        fi
    fi
    bash "$task_dir/autostart.sh" status
    printf 'listening / listening_manual_wakeup 表示等待提问，每轮仍需唤醒词。\n'
}

case ${1:-menu} in
    menu)
        printf '\n小爱手机助手\n1. 配置账号和模型\n2. 启动\n3. 查看状态\n4. 停止\n5. 重启\n6. 开机自启状态\n0. 退出\n'
        read -r -p '选择：' choice
        case "$choice" in
            1) exec bash "$0" configure ;;
            2) exec bash "$0" start ;;
            3) exec bash "$0" status ;;
            4) exec bash "$0" stop ;;
            5) exec bash "$0" restart ;;
            6) exec bash "$0" autostart status ;;
            0) exit 0 ;;
            *) printf '请输入 0 到 6。\n'; exit 2 ;;
        esac ;;
    configure)
        bash "$task_dir/stop.sh"
        exec bash "$task_dir/open-configure.sh" "${@:2}" ;;
    start) exec bash "$task_dir/start.sh" ;;
    stop) exec bash "$task_dir/stop.sh" ;;
    status) show_status ;;
    autostart) exec bash "$task_dir/autostart.sh" "${2:-status}" ;;
    restart) bash "$task_dir/stop.sh"; exec bash "$task_dir/start.sh" ;;
    apply-settings)
        bash "$task_dir/stop.sh"
        run_python tune-voice.py
        exec bash "$task_dir/start.sh" ;;
    check-stream) run_python check-stream.py ;;
    voice-sample) run_python diagnose-voice.py ;;
    help|--help|-h)
        printf 'xiaoai [configure|start|stop|status|restart|autostart|apply-settings|check-stream|voice-sample]\n'
        printf 'xiaoai autostart [enable|disable|status] 管理 Termux:Boot 开机脚本。\n'
        printf 'check-stream 调用一次模型 API；voice-sample 通过微软合成固定样本并在音箱播放。\n' ;;
    *) printf '未知命令。输入 xiaoai help 查看帮助。\n' >&2; exit 2 ;;
esac
