"""One clock for the whole build, so that run.sh gives the same files on every run.

CASEFOLD_ON   the date the rules and the expected answers are taken for (YYYY-MM-DD); default: today
CASEFOLD_NOW  the moment written into the files as 'built', 'at' or 'made' (ISO 8601, e.g. 2026-11-14T09:00:00Z);
              default: CASEFOLD_ON at 09:00 UTC when that is set, otherwise the real time

run.sh sets both to a fixed day, so a rebuild changes no committed file unless the data or the code changed.
Outside run.sh (the MCP server, a compliance officer working on a real file) neither is set and the real clock is used.
"""
import os
from datetime import date, datetime, timezone


def today():
    s = os.environ.get('CASEFOLD_ON')
    return date.fromisoformat(s) if s else date.today()


def now():
    s = os.environ.get('CASEFOLD_NOW')
    if s:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    if os.environ.get('CASEFOLD_ON'):
        return datetime.combine(today(), datetime.min.time().replace(hour=9), tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def stamp():
    """now() as 2026-11-14T09:00:00Z, the form the files use."""
    return now().strftime('%Y-%m-%dT%H:%M:%SZ')
