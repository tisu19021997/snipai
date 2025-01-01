from enum import StrEnum
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional


class TimeFilter(StrEnum):
    ALL_TIME = "All time"
    TODAY = "Today"
    YESTERDAY = "Yesterday"
    THIS_WEEK = "This week"

    def to_date_range(self):
        """Convert a string time range filter to a tuple of datetime objects representing the start and end of the range."""
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        match self:
            case TimeFilter.TODAY:
                return today_start, now
            case TimeFilter.YESTERDAY:
                yesterday_start = today_start - timedelta(days=1)
                return yesterday_start, today_start
            case TimeFilter.THIS_WEEK:
                days_since_monday = now.weekday()
                week_start = today_start - timedelta(days=days_since_monday)
                return week_start, now
            case TimeFilter.ALL_TIME:
                return None, None
            case _:
                raise ValueError(f"Invalid time filter: {self}")
