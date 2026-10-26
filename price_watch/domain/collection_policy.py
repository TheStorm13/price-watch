"""Pure scheduling and ownership time policy; callers provide the clock."""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CollectionPolicy:
    full_interval: timedelta = timedelta(hours=6)
    stale_after: timedelta = timedelta(seconds=30)

    def __post_init__(self):
        object.__setattr__(self, 'stale_after', max(timedelta(seconds=15), self.stale_after))

    def full_collection_due(self, *, now: datetime, last_started_at: datetime | None,
                            has_active: bool) -> bool:
        return not has_active and (last_started_at is None or now - last_started_at >= self.full_interval)

    def stale_cutoff(self, now: datetime) -> datetime:
        return now - self.stale_after

    def is_stale(self, *, now: datetime, heartbeat_at: datetime | None, started_at: datetime) -> bool:
        return (heartbeat_at or started_at) < self.stale_cutoff(now)
