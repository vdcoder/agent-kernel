"""
Ocean Cruises — Dining Reservation MCP Server

Thin MCP wrapper around the REST API layer (dining_api.py).
All business logic lives in DiningRestAPI; these tools are pure
transport adapters that map MCP tool calls → REST-style API calls.

Usage:
    # stdio transport (for direct LLM integration)
    python mcp/dining_mcp_server.py

    # SSE transport (for network access)
    python mcp/dining_mcp_server.py --transport sse --port 8100
"""

import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from dining_api import DiningRestAPI

# ──────────────────────────────────────────────
# Server setup
# ──────────────────────────────────────────────

mcp = FastMCP(
    "Ocean Cruises Dining Reservations",
    instructions=(
        "You are the dining reservation system for the Ocean Ocean cruise ship. "
        "Use these tools to help guests view, create, modify, and cancel specialty "
        "dining reservations. Always confirm actions with the guest before making "
        "changes. Be warm and professional — this is a premium cruise experience."
    ),
)

api = DiningRestAPI()

# ──────────────────────────────────────────────
# MCP Tools  (each maps to one REST endpoint)
# ──────────────────────────────────────────────


@mcp.tool()
def list_restaurants() -> dict:
    """
    List all specialty dining restaurants on the Ocean Ocean.

    Returns details for each restaurant including name, cuisine type,
    cover charge per person, operating hours, deck location, and seating capacity.

    Maps to → GET /api/v1/restaurants
    """
    return api.get_restaurants()


@mcp.tool()
def get_restaurant_details(venue_id: str) -> dict:
    """
    Get full details for a specific specialty restaurant.

    Args:
        venue_id: The restaurant identifier (DIN001 through DIN005).
                  DIN001=The Steakhouse, DIN002=La Trattoria, DIN003=Le Bistro,
                  DIN004=Sakura, DIN005=Chef's Table

    Maps to → GET /api/v1/restaurants/{venue_id}
    """
    return api.get_restaurant(venue_id)


@mcp.tool()
def check_availability(venue_id: str, date: str) -> dict:
    """
    Check availability for a specialty restaurant on a specific date.

    Returns remaining capacity and available time slots.

    Args:
        venue_id: Restaurant identifier (DIN001–DIN005)
        date: Date to check in YYYY-MM-DD format (e.g., '2026-02-08')

    Maps to → GET /api/v1/restaurants/{venue_id}/availability?date=YYYY-MM-DD
    """
    return api.get_restaurant_availability(venue_id, date)


@mcp.tool()
def list_reservations(
    guest_id: Optional[str] = None,
    venue_id:  Optional[str] = None,
    date:      Optional[str] = None,
    status:    Optional[str] = None,
) -> dict:
    """
    List dining reservations with optional filters.

    Call with no arguments to list all reservations, or filter by any combination
    of guest_id, venue_id, date, or status.

    Args:
        guest_id: Filter by guest (e.g., 'G100001'). Recommended for guest-specific queries.
        venue_id: Filter by restaurant (e.g., 'DIN001')
        date: Filter by reservation date (YYYY-MM-DD)
        status: Filter by status ('Confirmed' or 'Cancelled')

    Maps to → GET /api/v1/reservations?guest_id=&venue_id=&date=&status=
    """
    return api.get_reservations(guest_id=guest_id, venue_id=venue_id, date=date, status=status)


@mcp.tool()
def get_reservation(reservation_id: str) -> dict:
    """
    Get full details of a specific reservation by its ID.

    Args:
        reservation_id: The reservation identifier (e.g., 'DRES000001')

    Maps to → GET /api/v1/reservations/{reservation_id}
    """
    return api.get_reservation(reservation_id)


@mcp.tool()
def create_reservation(
    guest_id:         str,
    guest_name:       str,
    cabin_number:     str,
    venue_id:         str,
    reservation_date: str,
    reservation_time: str,
    party_size:       int,
    special_requests: Optional[str] = None,
    dietary_notes:    Optional[str] = None,
) -> dict:
    """
    Create a new specialty dining reservation.

    IMPORTANT: Always confirm the details with the guest before calling this tool.

    Args:
        guest_id: Guest identifier (e.g., 'G100001')
        guest_name: Guest's full name (e.g., 'James Smith')
        cabin_number: Guest's cabin number
        venue_id: Restaurant identifier (DIN001–DIN005)
        reservation_date: Date in YYYY-MM-DD format
        reservation_time: Time in HH:MM 24-hour format (e.g., '19:00')
        party_size: Number of guests dining (1–8)
        special_requests: Optional notes (e.g., 'Anniversary dinner', 'Window table')
        dietary_notes: Optional dietary needs (e.g., 'Gluten-Free', 'Shellfish allergy')

    Maps to → POST /api/v1/reservations
    """
    return api.post_reservation({
        "guest_id":         guest_id,
        "guest_name":       guest_name,
        "cabin_number":     cabin_number,
        "venue_id":         venue_id,
        "reservation_date": reservation_date,
        "reservation_time": reservation_time,
        "party_size":       party_size,
        "special_requests": special_requests,
        "dietary_notes":    dietary_notes,
    })


@mcp.tool()
def modify_reservation(
    reservation_id:   str,
    reservation_date: Optional[str] = None,
    reservation_time: Optional[str] = None,
    party_size:       Optional[int] = None,
    special_requests: Optional[str] = None,
    dietary_notes:    Optional[str] = None,
) -> dict:
    """
    Modify an existing dining reservation.

    Only provide the fields you want to change — unchanged fields will be preserved.
    IMPORTANT: Always confirm the changes with the guest before calling this tool.

    Args:
        reservation_id: The reservation to modify (e.g., 'DRES000001')
        reservation_date: New date in YYYY-MM-DD format (optional)
        reservation_time: New time in HH:MM format (optional)
        party_size: New party size, 1–8 (optional)
        special_requests: Updated special requests (optional)
        dietary_notes: Updated dietary notes (optional)

    Maps to → PATCH /api/v1/reservations/{reservation_id}
    """
    body = {}
    if reservation_date is not None:
        body["reservation_date"] = reservation_date
    if reservation_time is not None:
        body["reservation_time"] = reservation_time
    if party_size is not None:
        body["party_size"] = party_size
    if special_requests is not None:
        body["special_requests"] = special_requests
    if dietary_notes is not None:
        body["dietary_notes"] = dietary_notes

    return api.patch_reservation(reservation_id, body)


@mcp.tool()
def cancel_reservation(reservation_id: str) -> dict:
    """
    Cancel a dining reservation.

    IMPORTANT: Always confirm cancellation with the guest before calling this tool.
    Cancellations within 4 hours of the reservation time may incur a fee.

    Args:
        reservation_id: The reservation to cancel (e.g., 'DRES000001')

    Maps to → DELETE /api/v1/reservations/{reservation_id}
    """
    return api.delete_reservation(reservation_id)


# ──────────────────────────────────────────────
# MCP Resources (read-only reference data)
# ──────────────────────────────────────────────


@mcp.resource("dining://restaurants")
def restaurants_resource() -> str:
    """Complete list of specialty dining restaurants and their details."""
    data  = api.get_restaurants()
    lines = ["# Specialty Dining Restaurants — Ocean Ocean\n"]
    for r in data["restaurants"]:
        lines.append(f"## {r['name']} ({r['venue_id']})")
        lines.append(f"- Cuisine: {r['cuisine']}")
        lines.append(f"- Cover Charge: ${r['cover_charge']:.2f} per person")
        lines.append(f"- Hours: {r['hours']}")
        lines.append(f"- Deck: {r['deck']}")
        lines.append(f"- Capacity: {r['capacity']} seats")
        lines.append("")
    return "\n".join(lines)


@mcp.resource("dining://policies")
def policies_resource() -> str:
    """Dining reservation policies and rules."""
    return """# Specialty Dining Reservation Policies

- Reservations are required for all specialty restaurants.
- Maximum party size: 8 guests per reservation.
- Cover charges are per person and charged to the guest's folio.
- Children under 12 receive 50% off cover charges.
- Cancellations within 4 hours of reservation time may incur a $10/person fee.
- Guests with Ocean Plus package: 1 complimentary specialty meal included.
- Guests with Ocean Premier package: 2 complimentary specialty meals included.
- Dietary accommodations: notify at booking or at least 24 hours in advance.
- Dress code: Smart Casual minimum. No shorts, tank tops, or flip-flops.
- Formal Night dress code applies on designated evenings.
"""


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    transport = "stdio"
    port = 8100

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        elif arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    if transport == "sse":
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")
