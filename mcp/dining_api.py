"""
Ocean Cruises — Dining REST API Layer

Pretend REST implementation that mirrors the following surface:

    GET    /api/v1/restaurants
    GET    /api/v1/restaurants/{venue_id}
    GET    /api/v1/restaurants/{venue_id}/availability?date=YYYY-MM-DD
    GET    /api/v1/reservations?guest_id=&venue_id=&date=&status=
    GET    /api/v1/reservations/{reservation_id}
    POST   /api/v1/reservations
    PATCH  /api/v1/reservations/{reservation_id}
    DELETE /api/v1/reservations/{reservation_id}

This module is transport-agnostic.  The MCP server (dining_mcp_server.py)
imports DiningRestAPI and calls through to it; in the future a real HTTP
framework (FastAPI, Flask …) could do the same.
"""

import csv
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

# ──────────────────────────────────────────────
# Static data
# ──────────────────────────────────────────────

_RESTAURANTS: dict[str, dict] = {
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

_AVAILABLE_TIMES = [
    "17:30", "18:00", "18:30", "19:00",
    "19:30", "20:00", "20:30", "21:00",
]

_CSV_FIELDNAMES = [
    "Reservation_ID", "Guest_ID", "Guest_Name", "Cabin_Number",
    "Venue_ID", "Venue_Name", "Reservation_Date", "Reservation_Time",
    "Party_Size", "Special_Requests", "Dietary_Notes", "Status",
    "Confirmation_Number", "Created_At", "Modified_At",
    "Cancelled_At", "Cancellation_Reason",
]


# ──────────────────────────────────────────────
# API error helpers
# ──────────────────────────────────────────────

def _not_found(resource: str, id_: str) -> dict:
    return {"error": f"{resource} '{id_}' not found", "status_code": 404}


def _bad_request(message: str) -> dict:
    return {"error": message, "status_code": 400}


def _ok(payload: dict) -> dict:
    return {**payload, "status_code": 200}


def _created(payload: dict) -> dict:
    return {**payload, "status_code": 201}


def _no_content() -> dict:
    return {"status_code": 204}


# ──────────────────────────────────────────────
# CSV persistence helpers
# ──────────────────────────────────────────────

def _csv_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "db", "dining_reservations.csv")
    )


def _load_csv() -> dict[str, dict]:
    path = _csv_path()
    reservations: dict[str, dict] = {}
    if not os.path.exists(path):
        print(f"[dining_api] Warning: {path} not found — starting with empty reservations",
              file=sys.stderr)
        return reservations
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = row["Reservation_ID"]
            reservations[rid] = {
                "reservation_id":    rid,
                "guest_id":          row["Guest_ID"],
                "guest_name":        row["Guest_Name"],
                "cabin_number":      row["Cabin_Number"],
                "venue_id":          row["Venue_ID"],
                "venue_name":        row["Venue_Name"],
                "reservation_date":  row["Reservation_Date"],
                "reservation_time":  row["Reservation_Time"],
                "party_size":        int(row["Party_Size"]),
                "special_requests":  row["Special_Requests"] or None,
                "dietary_notes":     row["Dietary_Notes"] or None,
                "status":            row["Status"],
                "confirmation_number": row["Confirmation_Number"],
                "created_at":        row.get("Created_At") or None,
                "modified_at":       row.get("Modified_At") or None,
                "cancelled_at":      row.get("Cancelled_At") or None,
                "cancellation_reason": row.get("Cancellation_Reason") or None,
            }
    print(f"[dining_api] Loaded {len(reservations)} reservations from CSV", file=sys.stderr)
    return reservations


def _save_csv(reservations: dict[str, dict]) -> None:
    path = _csv_path()
    tmp  = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for r in reservations.values():
            writer.writerow({
                "Reservation_ID":      r["reservation_id"],
                "Guest_ID":            r["guest_id"],
                "Guest_Name":          r["guest_name"],
                "Cabin_Number":        r["cabin_number"],
                "Venue_ID":            r["venue_id"],
                "Venue_Name":          r["venue_name"],
                "Reservation_Date":    r["reservation_date"],
                "Reservation_Time":    r["reservation_time"],
                "Party_Size":          r["party_size"],
                "Special_Requests":    r.get("special_requests") or "",
                "Dietary_Notes":       r.get("dietary_notes") or "",
                "Status":              r["status"],
                "Confirmation_Number": r["confirmation_number"],
                "Created_At":          r.get("created_at") or "",
                "Modified_At":         r.get("modified_at") or "",
                "Cancelled_At":        r.get("cancelled_at") or "",
                "Cancellation_Reason": r.get("cancellation_reason") or "",
            })
    os.replace(tmp, path)
    print(f"[dining_api] Saved {len(reservations)} reservations to CSV", file=sys.stderr)


# ──────────────────────────────────────────────
# REST API class
# ──────────────────────────────────────────────

class DiningRestAPI:
    """
    Transport-agnostic implementation of the Dining REST surface.

    Every public method maps 1-to-1 to a REST endpoint.  Each method
    returns a plain dict that always contains a ``status_code`` key so
    callers can check for errors without inspecting the shape of the body.

    Route mapping
    ─────────────
    GET  /api/v1/restaurants                              → get_restaurants()
    GET  /api/v1/restaurants/{venue_id}                   → get_restaurant(venue_id)
    GET  /api/v1/restaurants/{venue_id}/availability      → get_restaurant_availability(venue_id, date)
    GET  /api/v1/reservations                             → get_reservations(...)
    GET  /api/v1/reservations/{reservation_id}            → get_reservation(reservation_id)
    POST /api/v1/reservations                             → post_reservation(body)
    PATCH/api/v1/reservations/{reservation_id}            → patch_reservation(reservation_id, body)
    DELETE/api/v1/reservations/{reservation_id}           → delete_reservation(reservation_id)
    """

    def __init__(self) -> None:
        self._restaurants: dict[str, dict] = _RESTAURANTS
        self._reservations: dict[str, dict] = _load_csv()

    # ── GET /api/v1/restaurants ────────────────────────────────────────────

    def get_restaurants(self) -> dict:
        """List all specialty restaurants."""
        return _ok({
            "restaurants": list(self._restaurants.values()),
            "count":       len(self._restaurants),
        })

    # ── GET /api/v1/restaurants/{venue_id} ────────────────────────────────

    def get_restaurant(self, venue_id: str) -> dict:
        """Retrieve a single restaurant by venue_id."""
        if venue_id not in self._restaurants:
            return _not_found("Restaurant", venue_id)
        return _ok(self._restaurants[venue_id])

    # ── GET /api/v1/restaurants/{venue_id}/availability?date=YYYY-MM-DD ──

    def get_restaurant_availability(self, venue_id: str, date: str) -> dict:
        """Check seat availability for a restaurant on a given date."""
        if venue_id not in self._restaurants:
            return _not_found("Restaurant", venue_id)

        restaurant = self._restaurants[venue_id]
        confirmed  = [
            r for r in self._reservations.values()
            if r["venue_id"]          == venue_id
            and r["reservation_date"] == date
            and r["status"]           == "Confirmed"
        ]
        total_covers = sum(r["party_size"] for r in confirmed)
        capacity     = restaurant["capacity"]
        booked_times = [r["reservation_time"] for r in confirmed]
        max_per_slot = max(1, capacity // (len(_AVAILABLE_TIMES) * 2))

        return _ok({
            "venue_id":            venue_id,
            "restaurant":          restaurant["name"],
            "date":                date,
            "total_reservations":  len(confirmed),
            "total_covers":        total_covers,
            "remaining_capacity":  max(0, capacity - total_covers),
            "available_times": [
                t for t in _AVAILABLE_TIMES
                if booked_times.count(t) < max_per_slot
            ],
            "fully_booked": total_covers >= capacity,
        })

    # ── GET /api/v1/reservations?guest_id=&venue_id=&date=&status= ────────

    def get_reservations(
        self,
        guest_id: Optional[str] = None,
        venue_id:  Optional[str] = None,
        date:      Optional[str] = None,
        status:    Optional[str] = None,
    ) -> dict:
        """List reservations with optional query-string filters."""
        results = list(self._reservations.values())
        if guest_id:
            results = [r for r in results if r["guest_id"] == guest_id]
        if venue_id:
            results = [r for r in results if r["venue_id"] == venue_id]
        if date:
            results = [r for r in results if r["reservation_date"] == date]
        if status:
            results = [r for r in results if r["status"].lower() == status.lower()]
        return _ok({"reservations": results, "count": len(results)})

    # ── GET /api/v1/reservations/{reservation_id} ─────────────────────────

    def get_reservation(self, reservation_id: str) -> dict:
        """Retrieve a single reservation by ID."""
        if reservation_id not in self._reservations:
            return _not_found("Reservation", reservation_id)
        return _ok(self._reservations[reservation_id])

    # ── POST /api/v1/reservations ─────────────────────────────────────────

    def post_reservation(self, body: dict[str, Any]) -> dict:
        """
        Create a new reservation.

        Expected body keys:
            guest_id, guest_name, cabin_number, venue_id,
            reservation_date, reservation_time, party_size,
            special_requests (optional), dietary_notes (optional)
        """
        venue_id    = body.get("venue_id", "")
        party_size  = body.get("party_size", 0)

        if venue_id not in self._restaurants:
            return _bad_request(
                f"Invalid venue_id. Valid options: {', '.join(self._restaurants)}"
            )
        if not isinstance(party_size, int) or not 1 <= party_size <= 8:
            return _bad_request("party_size must be an integer between 1 and 8")

        restaurant   = self._restaurants[venue_id]
        confirmed    = [
            r for r in self._reservations.values()
            if r["venue_id"]          == venue_id
            and r["reservation_date"] == body.get("reservation_date")
            and r["status"]           == "Confirmed"
        ]
        total_covers = sum(r["party_size"] for r in confirmed)
        remaining    = restaurant["capacity"] - total_covers

        if party_size > remaining:
            return _bad_request(
                f"Insufficient capacity at {restaurant['name']} on "
                f"{body.get('reservation_date')}. Only {remaining} seats remaining."
            )

        rid  = f"DRES{len(self._reservations) + 1:06d}"
        conf = f"DIN-{uuid.uuid4().hex[:5].upper()}"
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        reservation: dict[str, Any] = {
            "reservation_id":      rid,
            "guest_id":            body["guest_id"],
            "guest_name":          body["guest_name"],
            "cabin_number":        body["cabin_number"],
            "venue_id":            venue_id,
            "venue_name":          restaurant["name"],
            "reservation_date":    body["reservation_date"],
            "reservation_time":    body["reservation_time"],
            "party_size":          party_size,
            "special_requests":    body.get("special_requests"),
            "dietary_notes":       body.get("dietary_notes"),
            "status":              "Confirmed",
            "confirmation_number": conf,
            "created_at":          now,
            "modified_at":         None,
            "cancelled_at":        None,
            "cancellation_reason": None,
        }
        self._reservations[rid] = reservation
        _save_csv(self._reservations)

        return _created({
            "message":              f"Reservation confirmed at {restaurant['name']}",
            "reservation":          reservation,
            "cover_charge_per_person": restaurant["cover_charge"],
            "estimated_total":      restaurant["cover_charge"] * party_size,
        })

    # ── PATCH /api/v1/reservations/{reservation_id} ───────────────────────

    def patch_reservation(self, reservation_id: str, body: dict[str, Any]) -> dict:
        """
        Partially update an existing reservation.

        Accepted body keys (all optional):
            reservation_date, reservation_time, party_size,
            special_requests, dietary_notes
        """
        if reservation_id not in self._reservations:
            return _not_found("Reservation", reservation_id)

        reservation = self._reservations[reservation_id]

        if reservation["status"] == "Cancelled":
            return _bad_request("Cannot modify a cancelled reservation. Please create a new one.")

        changes: dict[str, dict] = {}

        if "reservation_date" in body:
            changes["reservation_date"] = {
                "from": reservation["reservation_date"], "to": body["reservation_date"]
            }
            reservation["reservation_date"] = body["reservation_date"]

        if "reservation_time" in body:
            changes["reservation_time"] = {
                "from": reservation["reservation_time"], "to": body["reservation_time"]
            }
            reservation["reservation_time"] = body["reservation_time"]

        if "party_size" in body:
            ps = body["party_size"]
            if not isinstance(ps, int) or not 1 <= ps <= 8:
                return _bad_request("party_size must be an integer between 1 and 8")
            changes["party_size"] = {"from": reservation["party_size"], "to": ps}
            reservation["party_size"] = ps

        if "special_requests" in body:
            changes["special_requests"] = {
                "from": reservation["special_requests"], "to": body["special_requests"]
            }
            reservation["special_requests"] = body["special_requests"]

        if "dietary_notes" in body:
            changes["dietary_notes"] = {
                "from": reservation["dietary_notes"], "to": body["dietary_notes"]
            }
            reservation["dietary_notes"] = body["dietary_notes"]

        if not changes:
            return _bad_request("No recognised fields in request body. Nothing was changed.")

        reservation["modified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_csv(self._reservations)

        return _ok({
            "message":     "Reservation updated successfully",
            "changes":     changes,
            "reservation": reservation,
        })

    # ── DELETE /api/v1/reservations/{reservation_id} ──────────────────────

    def delete_reservation(self, reservation_id: str) -> dict:
        """Cancel (soft-delete) a reservation."""
        if reservation_id not in self._reservations:
            return _not_found("Reservation", reservation_id)

        reservation = self._reservations[reservation_id]

        if reservation["status"] == "Cancelled":
            return _bad_request("This reservation is already cancelled.")

        reservation["status"]       = "Cancelled"
        reservation["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_csv(self._reservations)

        return _ok({
            "message": (
                f"Reservation at {reservation['venue_name']} on "
                f"{reservation['reservation_date']} at "
                f"{reservation['reservation_time']} has been cancelled."
            ),
            "reservation_id":      reservation_id,
            "confirmation_number": reservation["confirmation_number"],
        })
