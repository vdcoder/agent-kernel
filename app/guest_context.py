"""StaticContextProvider that injects the active guest's profile into the system prompt."""
from __future__ import annotations

from src.interfaces import StaticContextProvider
from app.runtime import AppRuntime


class GuestProfileProvider(StaticContextProvider):
    """Renders the guest profile stored in rt.state.guest_profile for the LLM.

    Placed in the static context (good KV-cache candidate) because the profile
    does not change within a session.
    """

    def __init__(self, rt: AppRuntime) -> None:
        self._rt = rt

    def get(self) -> str:
        p = self._rt.state.guest_profile
        if not p:
            return ""

        # Format dates as readable range
        voyage = f"{p.get('Embark_Date', '?')} → {p.get('Debark_Date', '?')}"

        lines = [
            "## Active Guest Profile",
            f"ID          : {p.get('Guest_ID', '?')}",
            f"Name        : {p.get('First_Name', '')} {p.get('Last_Name', '')}",
            f"Cabin       : {p.get('Cabin_Number', '?')}  ({p.get('Cabin_Category', '?')}, Deck {p.get('Deck', '?')})",
            f"Party size  : {p.get('Party_Size', '?')}",
            f"Voyage      : {voyage}",
            f"Loyalty     : {p.get('Loyalty_Tier', '?')} — {p.get('Loyalty_Points', 0):,} pts  |  Past cruises: {p.get('Past_Cruises', 0)}",
            f"Dietary     : {p.get('Dietary_Restrictions', 'None') or 'None'}",
            f"Occasions   : {p.get('Special_Occasions', 'None') or 'None'}",
            f"Bev package : {p.get('Beverage_Package', 'None') or 'None'}",
        ]
        return "\n".join(lines)
