import multiprocessing
import os
import time


def burn_cpu():
    x = 0
    while True:
        x = (x * 1103515245 + 12345) % (2**31)


def main():
    cpu_workers = int(os.environ.get("CPU_WORKERS", "1"))
    memory_mb = int(os.environ.get("MEMORY_MB", "100"))

    workers = [multiprocessing.Process(target=burn_cpu, daemon=True) for _ in range(cpu_workers)]
    for w in workers:
        w.start()

    block = bytearray(memory_mb * 1024 * 1024)
    for i in range(0, len(block), 4096):
        block[i] = 1

    print(f"batch stub: {cpu_workers} cpu workers, {memory_mb}MiB held", flush=True)

    while True:
        time.sleep(30)
        print("batch stub: still burning", flush=True)


if __name__ == "__main__":
    main()
