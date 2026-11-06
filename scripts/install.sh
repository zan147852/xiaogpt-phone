#!/data/data/com.termux/files/usr/bin/bash
# Install the public project into Termux's private app storage.
set -euo pipefail
umask 077

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task_dir=/data/data/com.termux/files/home/xiaogpt
prefix_dir=/data/data/com.termux/files/usr

if [[ ${PREFIX:-} != "$prefix_dir" ]]; then
    printf '请在 Android 的 Termux 中运行：bash scripts/install.sh\n' >&2
    exit 2
fi
if [[ $(uname -m) != aarch64 ]]; then
    printf '当前安装入口仅支持 ARM64（aarch64）手机。\n' >&2
    exit 2
fi

printf '1/4 安装 Termux 依赖（首次下载可能较慢）\n'
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y -o Dpkg::Options::=--force-confold curl proot-distro
if ! proot-distro install --help | grep -q -- '--name'; then
    printf '需要支持 --name 的 PRoot-Distro 5.x，请先 pkg upgrade proot-distro。\n' >&2
    exit 2
fi

mkdir -p "$task_dir"
# A running service must not load a half-updated set of Python modules.
if [[ -f "$task_dir/service.lock" ]]; then
    exec 8>"$task_dir/service.lock"
    if ! flock -n 8; then
        printf '服务正在运行。请先 xiaoai stop，再重新安装；原配置和记忆会保留。\n' >&2
        exit 2
    fi
fi

printf '2/4 准备 Ubuntu 24.04 ARM64\n'
if ! proot-distro list --quiet | grep -Fxq xiaogpt; then
    archive="$task_dir/ubuntu-base-24.04.3-base-arm64.tar.gz"
    archive_url=https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.3-base-arm64.tar.gz
    archive_hash=7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --retry 3 --output "$archive.part" "$archive_url"
        mv -- "$archive.part" "$archive"
    fi
    printf '%s  %s\n' "$archive_hash" "$archive" | sha256sum --check --status || {
        printf 'Ubuntu 文件校验失败，未安装。请移走 %s 后重新下载。\n' "$archive" >&2
        exit 1
    }
    proot-distro install "$archive" --name xiaogpt
fi

printf '3/4 复制代码并安装 Python 依赖\n'
if [[ -f "$task_dir/run.py" ]]; then
    backup_dir="$task_dir/rollback-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    for source in "$task_dir"/*.py "$task_dir"/*.sh "$task_dir/requirements.txt"; do
        [[ ! -f "$source" ]] || cp -p -- "$source" "$backup_dir/"
    done
fi
cp -- "$repo_dir"/app/*.py "$repo_dir"/phone/*.sh "$repo_dir/requirements.txt" "$task_dir/"
chmod 600 "$task_dir"/*.py "$task_dir"/*.sh "$task_dir/requirements.txt"
# A pre-existing configuration is not considered checked by a fresh install.
previous_status=$(cat "$task_dir/setup-status" 2>/dev/null || true)
printf 'installing_runtime\n' > "$task_dir/setup-status"
if ! proot-distro login --bind "$task_dir:/opt/xiaogpt" xiaogpt -- /bin/bash /opt/xiaogpt/setup-runtime.sh; then
    printf 'runtime_install_failed\n' > "$task_dir/setup-status"
    printf '依赖安装失败；原配置和记忆未删除。检查网络后重新执行安装。\n' >&2
    exit 1
fi
if [[ $previous_status == configured_checks_passed ]]; then
    proot-distro login --bind "$task_dir:/opt/xiaogpt" xiaogpt -- \
        /root/xiaogpt-venv/bin/python /opt/xiaogpt/tune-voice.py
    printf 'configured_checks_passed\n' > "$task_dir/setup-status"
else
    printf 'runtime_ready\n' > "$task_dir/setup-status"
fi

printf '4/4 安装 xiaoai 命令\n'
cat > "$prefix_dir/bin/xiaoai" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
exec bash /data/data/com.termux/files/home/xiaogpt/xiaoai.sh "$@"
SH
chmod 700 "$prefix_dir/bin/xiaoai"
printf '\n安装完成。输入 xiaoai 打开菜单，首次使用选择“配置”。\n'
printf '升级后输入 xiaoai start 启动；保留账号与记忆，公开语音偏好按当前版本更新。\n'
