#!/usr/bin/env bash
set -euo pipefail

# Run as the host user: only cgroup setup needs sudo.
if (( EUID == 0 )); then
    echo "Запусти скрипт обычным пользователем, без sudo." >&2
    exit 1
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

for command_name in sudo unshare capsh ip hostname stat; do
    if ! command -v "$command_name" >/dev/null; then
        echo "Не найдена команда: $command_name" >&2
        exit 1
    fi
done

if [[ ! -x api/api || ! -x seccomp-run || ! -r seccomp-deny.txt ]]; then
    echo "Нужны собранные api/api, seccomp-run и профиль seccomp-deny.txt." >&2
    exit 1
fi

if [[ $(stat -fc %T /sys/fs/cgroup) != cgroup2fs ]]; then
    echo "Для запуска нужна cgroup v2 в /sys/fs/cgroup." >&2
    exit 1
fi

# A separate group for each run; do not reuse the manual experiment group.
script_pid=$$
cgroup_path="/sys/fs/cgroup/pandarecovery-$script_pid"
sudo -v

sudo sh -eu -c '
    group="/sys/fs/cgroup/pandarecovery-$1"
    mkdir "$group"
    echo 134217728 > "$group/memory.max"
    echo 0 > "$group/memory.swap.max"
    echo "50000 100000" > "$group/cpu.max"
    echo 32 > "$group/pids.max"

    # Move the calling script, not this privileged helper, into the group.
    # Its future children will inherit the same cgroup.
    echo "$1" > "$group/cgroup.procs"
' sh "$script_pid"

echo "Cgroup: $cgroup_path"
echo "Лимиты: 128 МиБ RAM, без swap, 0.5 CPU, 32 задачи."

# exec preserves cgroup membership. The child becomes PID 1 inside.
exec unshare --user --map-root-user \
    --pid --fork --kill-child \
    --mount --mount-proc \
    --net --uts --ipc \
    sh -eu -c '
        hostname pandarecovery
        ip link set lo up
        exec capsh --drop=all -- -c "
            exec ./seccomp-run ./seccomp-deny.txt ./api/api
        "
    '
