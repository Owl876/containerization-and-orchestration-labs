import multiprocessing
import os
import time


def burn_cpu():
    x = 0
    while True:
        x = (x * 1103515245 + 12345) % (2**31)


def touch(block):
    for i in range(0, len(block), 4096):
        block[i] = 1


def main():
    cpu_workers = int(os.environ.get("CPU_WORKERS", "1"))
    memory_mb = int(os.environ.get("MEMORY_MB", "100"))
    grow_mb_per_sec = int(os.environ.get("GROW_MB_PER_SEC", "0"))

    workers = [multiprocessing.Process(target=burn_cpu, daemon=True) for _ in range(cpu_workers)]
    for w in workers:
        w.start()

    held = []
    if grow_mb_per_sec <= 0:
        block = bytearray(memory_mb * 1024 * 1024)
        touch(block)
        held.append(block)
    else:
        # «утечка»: по 1 МиБ, чтобы kubelet успевал заметить давление на ноде раньше, чем та упрётся в потолок
        for _ in range(memory_mb):
            block = bytearray(1024 * 1024)
            touch(block)
            held.append(block)
            time.sleep(1 / grow_mb_per_sec)

    print(f"batch stub: {cpu_workers} cpu workers, {memory_mb}MiB held", flush=True)

    while True:
        time.sleep(30)
        print("batch stub: still burning", flush=True)


if __name__ == "__main__":
    main()
