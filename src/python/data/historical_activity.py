"""Re-export from mission_data.historical_activity for backwards compatibility."""

from mission_data.historical_activity import (
    HISTORICAL_LOG,
    AdversaryActivity,
    get_activity_summary,
    get_sector_activity,
)

__all__ = [
    "AdversaryActivity",
    "get_sector_activity",
    "get_activity_summary",
    "HISTORICAL_LOG",
]
