"""Re-export from mission_data.historical_activity for backwards compatibility."""

from mission_data.historical_activity import (
    AdversaryActivity,
    get_sector_activity,
    get_activity_summary,
    HISTORICAL_LOG,
)

__all__ = [
    "AdversaryActivity",
    "get_sector_activity",
    "get_activity_summary",
    "HISTORICAL_LOG",
]
