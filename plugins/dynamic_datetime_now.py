"""Dynamic context provider that injects the current date and time."""
from __future__ import annotations

from datetime import datetime

from src.interfaces import DynamicContextProvider


class DatetimeNowProvider(DynamicContextProvider):
    """Injects the current local date and time into the system prompt each turn.

    Keeps the model grounded in the present without requiring the user to
    state the date manually.
    """

    def get(self) -> str:
        now = datetime.now()
        return f"Current date and time: {now.strftime('%A, %B %d, %Y at %H:%M')}"
