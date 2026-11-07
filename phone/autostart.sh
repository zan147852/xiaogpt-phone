#!/data/data/com.termux/files/usr/bin/bash
# Manage only this project's hook, leaving other Termux:Boot scripts untouched.
set -euo pipefail
umask 077
task_dir=/data/data/com.termux/files/home/xiaogpt
boot_dir=/data/data/com.termux/files/home/.termux/boot
hook="$boot_dir/20-xiaogpt"

case ${1:-status} in
    enable)
        if ! /system/bin/pm path com.termux.boot 2>/dev/null | grep -q '^package:'; then
            printf '请先安装与 Termux 同来源、同签名的官方 Termux:Boot，并打开一次。\n' >&2
            exit 2
        fi
        if [[ $(cat "$task_dir/setup-status" 2>/dev/null) != configured_checks_passed ]]; then
            printf '请先完成 xiaoai configure 的连接验证。\n' >&2
            exit 2
        fi
        mkdir -p "$boot_dir"
        cat > "$hook.new" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
# Managed by XiaoGPT Phone. Disable with: xiaoai autostart disable
exec bash /data/data/com.termux/files/home/xiaogpt/boot-start.sh
SH
        chmod 700 "$hook.new"
        mv -f -- "$hook.new" "$hook"
        printf '开机自启脚本已启用。请打开 Termux:Boot 一次，并允许其系统自启动。\n'
        printf '重启并首次解锁、联网后再测试；系统后台限制可能影响执行。\n' ;;
    disable)
        if [[ -f "$hook" ]]; then
            mv -f -- "$hook" "$task_dir/boot-hook.disabled"
        fi
        printf '已关闭下次开机自启；当前问答服务保持原状态。\n' ;;
    status)
        if [[ -f "$hook" ]]; then
            printf '开机自启脚本：已启用\n'
        else
            printf '开机自启脚本：未启用\n'
        fi
        if /system/bin/pm path com.termux.boot 2>/dev/null | grep -q '^package:'; then
            printf 'Termux:Boot：已安装（仍需打开一次及系统后台权限）\n'
        else
            printf 'Termux:Boot：未安装\n'
        fi
        if [[ -f "$task_dir/boot-status" ]]; then
            printf '最近开机启动阶段：'; cat "$task_dir/boot-status"
        fi ;;
    *) printf '用法：xiaoai autostart [enable|disable|status]\n' >&2; exit 2 ;;
esac
