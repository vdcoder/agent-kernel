"""
Ocean Cruises — Dining Reservation MCP Server

A Model Context Protocol server exposing specialty dining reservation
tools for the Ocean Ocean onboard AI assistant.

Usage:
    # stdio transport (for direct LLM integration)
    python mcp/dining_mcp_server.py

    # SSE transport (for network access)
    python mcp/dining_mcp_server.py --transport sse --port 8100
"""

import csv
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

from mcp.server.fastmcp import FastMCP

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

# ──────────────────────────────────────────────
# Data stores
# ──────────────────────────────────────────────

RESTAURANTS = {
    "DIN001": {
        "venue_id": "DIN001",
        "name": "The Steakhouse",
        "cuisine": "Premium steaks & seafood",
        "cover_charge": 65.00,
        "hours": "17:30–21:30",
        "deck": 10,
        "capacity": 60,
    },
    "DIN002": {
        "venue_id": "DIN002",
        "name": "La Trattoria",
        "cuisine": "Italian multi-course tasting",
        "cover_charge": 45.00,
        "hours": "17:30–21:30",
        "deck": 10,
        "capacity": 80,
    },
    "DIN003": {
        "venue_id": "DIN003",
        "name": "Le Bistro",
        "cuisine": "French bistro",
        "cover_charge": 55.00,
        "hours": "17:30–21:30",
        "deck": 11,
        "capacity": 50,
    },
    "DIN004": {
        "venue_id": "DIN004",
        "name": "Sakura",
        "cuisine": "Japanese sushi & teppanyaki",
        "cover_charge": 50.00,
        "hours": "17:30–21:30",
        "deck": 11,
        "capacity": 45,
    },
    "DIN005": {
        "venue_id": "DIN005",
        "name": "Chef's Table",
        "cuisine": "Multi-course chef's tasting",
        "cover_charge": 95.00,
        "hours": "18:00–21:00",
        "deck": 12,
        "capacity": 24,
    },
}

RESERVATIONS: dict[str, dict] = {}

_CSV_FIELDNAMES = [
    "Reservation_ID", "Guest_ID", "Guest_Name", "Cabin_Number",
    "Venue_ID", "Venue_Name", "Reservation_Date", "Reservation_Time",
    "Party_Size", "Special_Requests", "Dietary_Notes", "Status",
    "Confirmation_Number", "Created_At", "Modified_At",
    "Cancelled_At", "Cancellation_Reason",
]


def _csv_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "db", "dining_reservations.csv")
    )


def _load_seed_data():
    """Load existing reservations from db/dining_reservations.csv."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "db", "dining_reservations.csv")
    csv_path = os.path.normpath(csv_path)
    if not os.path.exists(csv_path):
        print(f"[dining_mcp] Warning: {csv_path} not found — starting with empty reservations", file=sys.stderr)
        return
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = row["Reservation_ID"]
            RESERVATIONS[rid] = {
                "reservation_id": rid,
                "guest_id": row["Guest_ID"],
                "guest_name": row["Guest_Name"],
                "cabin_number": row["Cabin_Number"],
                "venue_id": row["Venue_ID"],
                "venue_name": row["Venue_Name"],
                "reservation_date": row["Reservation_Date"],
                "reservation_time": row["Reservation_Time"],
                "party_size": int(row["Party_Size"]),
                "special_requests": row["Special_Requests"] or None,
                "dietary_notes": row["Dietary_Notes"] or None,
                "status": row["Status"],
                "confirmation_number": row["Confirmation_Number"],
                "created_at": row.get("Created_At") or None,
                "modified_at": row.get("Modified_At") or None,
                "cancelled_at": row.get("Cancelled_At") or None,
                "cancellation_reason": row.get("Cancellation_Reason") or None,
            }
    print(f"[dining_mcp] Loaded {len(RESERVATIONS)} reservations from CSV", file=sys.stderr)


def _save_reservations() -> None:
    """Rewrite the full CSV from the in-memory RESERVATIONS dict."""
    path = _csv_path()
    tmp  = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for r in RESERVATIONS.values():
            writer.writerow({
                "Reservation_ID":   r["reservation_id"],
                "Guest_ID":         r["guest_id"],
                "Guest_Name":       r["guest_name"],
                "Cabin_Number":     r["cabin_number"],
                "Venue_ID":         r["venue_id"],
                "Venue_Name":       r["venue_name"],
                "Reservation_Date": r["reservation_date"],
                "Reservation_Time": r["reservation_time"],
                "Party_Size":       r["party_size"],
                "Special_Requests": r.get("special_requests") or "",
                "Dietary_Notes":    r.get("dietary_notes") or "",
                "Status":           r["status"],
                "Confirmation_Number": r["confirmation_number"],
                "Created_At":       r.get("created_at") or "",
                "Modified_At":      r.get("modified_at") or "",
                "Cancelled_At":     r.get("cancelled_at") or "",
                "Cancellation_Reason": r.get("cancellation_reason") or "",
            })
    os.replace(tmp, path)
    print(f"[dining_mcp] Saved {len(RESERVATIONS)} reservations to CSV", file=sys.stderr)


_load_seed_data()


# ──────────────────────────────────────────────
# MCP Tools
# ──────────────────────────────────────────────


@mcp.tool()
def list_restaurants() -> dict:
    """
    List all specialty dining restaurants on the Ocean Ocean.

    Returns details for each restaurant including name, cuisine type,
    cover charge per person, operating hours, deck location, and seating capacity.
    """
    return {
        "restaurants": list(RESTAURANTS.values()),
        "count": len(RESTAURANTS),
    }


@mcp.tool()
def get_restaurant_details(venue_id: str) -> dict:
    """
    Get full details for a specific specialty restaurant.

    Args:
        venue_id: The restaurant identifier (DIN001 through DIN005).
                  DIN001=The Steakhouse, DIN002=La Trattoria, DIN003=Le Bistro,
                  DIN004=Sakura, DIN005=Chef's Table
    """
    if venue_id not in RESTAURANTS:
        return {"error": f"Restaurant '{venue_id}' not found. Valid IDs: {', '.join(RESTAURANTS.keys())}"}
    return RESTAURANTS[venue_id]


@mcp.tool()
def check_availability(venue_id: str, date: str) -> dict:
    """
    Check availability for a specialty restaurant on a specific date.

    Returns remaining capacity and available time slots.

    Args:
        venue_id: Restaurant identifier (DIN001–DIN005)
        date: Date to check in YYYY-MM-DD format (e.g., '2026-02-08')
    """
    if venue_id not in RESTAURANTS:
        return {"error": f"Restaurant '{venue_id}' not found. Valid IDs: {', '.join(RESTAURANTS.keys())}"}

    restaurant = RESTAURANTS[venue_id]
    confirmed = [
        r for r in RESERVATIONS.values()
        if r["venue_id"] == venue_id
        and r["reservation_date"] == date
        and r["status"] == "Confirmed"
    ]
    total_covers = sum(r["party_size"] for r in confirmed)
    capacity = restaurant["capacity"]

    available_slots = ["17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]
    booked_times = [r["reservation_time"] for r in confirmed]
    max_per_slot = max(1, capacity // (len(available_slots) * 2))

    return {
        "restaurant": restaurant["name"],
        "date": date,
        "total_reservations": len(confirmed),
        "total_covers": total_covers,
        "remaining_capacity": max(0, capacity - total_covers),
        "available_times": [t for t in available_slots if booked_times.count(t) < max_per_slot],
        "fully_booked": total_covers >= capacity,
    }


@mcp.tool()
def list_reservations(
    guest_id: Optional[str] = None,
    venue_id: Optional[str] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
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
    """
    results = list(RESERVATIONS.values())
    if guest_id:
        results = [r for r in results if r["guest_id"] == guest_id]
    if venue_id:
        results = [r for r in results if r["venue_id"] == venue_id]
    if date:
        results = [r for r in results if r["reservation_date"] == date]
    if status:
        results = [r for r in results if r["status"].lower() == status.lower()]
    return {"reservations": results, "count": len(results)}


@mcp.tool()
def get_reservation(reservation_id: str) -> dict:
    """
    Get full details of a specific reservation by its ID.

    Args:
        reservation_id: The reservation identifier (e.g., 'DRES000001')
    """
    if reservation_id not in RESERVATIONS:
        return {"error": f"Reservation '{reservation_id}' not found"}
    return RESERVATIONS[reservation_id]


@mcp.tool()
def create_reservation(
    guest_id: str,
    guest_name: str,
    cabin_number: str,
    venue_id: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    special_requests: Optional[str] = None,
    dietary_notes: Optional[str] = None,
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
    """
    if venue_id not in RESTAURANTS:
        return {"error": f"Invalid restaurant. Valid IDs: {', '.join(RESTAURANTS.keys())}"}

    if not 1 <= party_size <= 8:
        return {"error": "Party size must be between 1 and 8 guests"}

    restaurant = RESTAURANTS[venue_id]
    confirmed = [
        r for r in RESERVATIONS.values()
        if r["venue_id"] == venue_id
        and r["reservation_date"] == reservation_date
        and r["status"] == "Confirmed"
    ]
    total_covers = sum(r["party_size"] for r in confirmed)
    remaining = restaurant["capacity"] - total_covers

    if party_size > remaining:
        return {
            "error": f"Insufficient capacity at {restaurant['name']} on {reservation_date}. "
                     f"Only {remaining} seats remaining.",
            "suggestion": "Try a different date or restaurant.",
        }

    rid  = f"DRES{len(RESERVATIONS) + 1:06d}"
    conf = f"DIN-{uuid.uuid4().hex[:5].upper()}"

    reservation = {
        "reservation_id": rid,
        "guest_id": guest_id,
        "guest_name": guest_name,
        "cabin_number": cabin_number,
        "venue_id": venue_id,
        "venue_name": restaurant["name"],
        "reservation_date": reservation_date,
        "reservation_time": reservation_time,
        "party_size": party_size,
        "special_requests": special_requests,
        "dietary_notes": dietary_notes,
        "status": "Confirmed",
        "confirmation_number": conf,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "modified_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
    }
    RESERVATIONS[rid] = reservation
    _save_reservations()

    return {
        "message": f"Reservation confirmed at {restaurant['name']}",
        "reservation": reservation,
        "cover_charge_per_person": restaurant["cover_charge"],
        "estimated_total": restaurant["cover_charge"] * party_size,
    }


@mcp.tool()
def modify_reservation(
    reservation_id: str,
    reservation_date: Optional[str] = None,
    reservation_time: Optional[str] = None,
    party_size: Optional[int] = None,
    special_requests: Optional[str] = None,
    dietary_notes: Optional[str] = None,
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
    """
    if reservation_id not in RESERVATIONS:
        return {"error": f"Reservation '{reservation_id}' not found"}

    reservation = RESERVATIONS[reservation_id]

    if reservation["status"] == "Cancelled":
        return {"error": "Cannot modify a cancelled reservation. Please create a new one."}

    changes = {}

    if reservation_date is not None:
        changes["reservation_date"] = {"from": reservation["reservation_date"], "to": reservation_date}
        reservation["reservation_date"] = reservation_date
    if reservation_time is not None:
        changes["reservation_time"] = {"from": reservation["reservation_time"], "to": reservation_time}
        reservation["reservation_time"] = reservation_time
    if party_size is not None:
        if not 1 <= party_size <= 8:
            return {"error": "Party size must be between 1 and 8"}
        changes["party_size"] = {"from": reservation["party_size"], "to": party_size}
        reservation["party_size"] = party_size
    if special_requests is not None:
        changes["special_requests"] = {"from": reservation["special_requests"], "to": special_requests}
        reservation["special_requests"] = special_requests
    if dietary_notes is not None:
        changes["dietary_notes"] = {"from": reservation["dietary_notes"], "to": dietary_notes}
        reservation["dietary_notes"] = dietary_notes

    if not changes:
        return {"error": "No changes specified. Provide at least one field to update."}

    reservation["modified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_reservations()

    return {
        "message": "Reservation updated successfully",
        "changes": changes,
        "reservation": reservation,
    }


@mcp.tool()
def cancel_reservation(reservation_id: str) -> dict:
    """
    Cancel a dining reservation.

    IMPORTANT: Always confirm cancellation with the guest before calling this tool.
    Cancellations within 4 hours of the reservation time may incur a fee.

    Args:
        reservation_id: The reservation to cancel (e.g., 'DRES000001')
    """
    if reservation_id not in RESERVATIONS:
        return {"error": f"Reservation '{reservation_id}' not found"}

    reservation = RESERVATIONS[reservation_id]

    if reservation["status"] == "Cancelled":
        return {"error": "This reservation is already cancelled"}

    reservation["status"] = "Cancelled"
    reservation["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_reservations()

    return {
        "message": f"Reservation at {reservation['venue_name']} on {reservation['reservation_date']} "
                   f"at {reservation['reservation_time']} has been cancelled.",
        "reservation_id": reservation_id,
        "confirmation_number": reservation["confirmation_number"],
    }


# ──────────────────────────────────────────────
# MCP Resources (read-only reference data)
# ──────────────────────────────────────────────


@mcp.resource("dining://restaurants")
def restaurants_resource() -> str:
    """Complete list of specialty dining restaurants and their details."""
    lines = ["# Specialty Dining Restaurants — Ocean Ocean\n"]
    for r in RESTAURANTS.values():
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
