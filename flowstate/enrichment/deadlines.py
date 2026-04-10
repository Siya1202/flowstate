from datetime import datetime, timedelta
import pytz
from dateutil.parser import parse
from typing import Optional

IST = pytz.timezone("Asia/Kolkata")

def normalize_deadline(relative_deadline: Optional[str], reference_date: datetime = None) -> Optional[str]:
    """
    Convert relative deadlines to absolute ISO timestamps in IST.
    Examples:
      "next Friday" → "2026-03-27T23:59:00+05:30"
      "EOD"         → "2026-03-24T18:00:00+05:30"
    """
    if not relative_deadline:
        return None

    now = datetime.now(IST) if not reference_date else reference_date.astimezone(IST)
    deadline = relative_deadline.lower().strip()

    # Handle common relative terms
    if deadline == "eod":
        return now.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()
    elif deadline == "eow":
        return (now + timedelta(days=(4 - now.weekday()) % 7)).replace(hour=18, minute=0, second=0).isoformat()
    elif "next" in deadline:
        if "friday" in deadline:
            next_friday = now + timedelta(days=(4 - now.weekday()) % 7 + 7)
            return next_friday.replace(hour=23, minute=59, second=0).isoformat()
        elif "monday" in deadline:
            next_monday = now + timedelta(days=(0 - now.weekday()) % 7 + 7)
            return next_monday.replace(hour=23, minute=59, second=0).isoformat()
    else:
        # Try parsing as a direct date/time
        try:
            dt = parse(relative_deadline, ignoretz=True).astimezone(IST)
            return dt.isoformat()
        except ValueError:
            return None