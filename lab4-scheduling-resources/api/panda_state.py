import asyncio
import time


class PandaState:
    """Энергия панды: тратится на /slow (сон) и /load (набежавшие туристы),
    восстанавливается сама собой со временем."""

    def __init__(self, max_energy: float = 100.0, regen_per_second: float = 1.0):
        self.max_energy = max_energy
        self.regen_per_second = regen_per_second
        self._energy = max_energy
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _regen_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_update
        self._energy = min(self.max_energy, self._energy + elapsed * self.regen_per_second)
        self._last_update = now

    async def spend(self, amount: float) -> float:
        async with self._lock:
            self._regen_locked()
            self._energy = max(0.0, self._energy - amount)
            return self._energy

    async def current(self) -> float:
        async with self._lock:
            self._regen_locked()
            return self._energy
