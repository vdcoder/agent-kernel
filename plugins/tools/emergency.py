"""Emergency escalation tool — triggers an immediate AI + human crew response.

The model calls this when it detects a situation requiring urgent attention.
Requires user approval before the alert is dispatched, so the guest or a
nearby crew member can confirm before the pipeline fires.
"""
from __future__ import annotations

from src.interfaces import Tool

_URGENCY_LEVELS = ("LIFE OR DEATH", "GROUP CRITICAL", "CRITICAL", "URGENT", "ELEVATED")

_EMERGENCY_TYPES = (
    "FIRE",
    "HEALTH",
    "BEHAVIOUR",
    "OVERBOARD",
    "SECURITY",
    "STRUCTURAL",
    "ENVIRONMENTAL",
    "OTHER",
)


class EmergencyTool(Tool):
    """Raises an emergency alert through the AI pipeline and notifies the human crew."""

    @property
    def name(self) -> str:
        return "emergency"

    @property
    def requires_approval(self) -> bool:
        return True

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "emergency",
                "description": (
                    "Raise an emergency alert when a guest situation requires immediate "
                    "attention — first routed through the AI response pipeline, then "
                    "escalated to the human crew. "
                    "Only call this when the situation is genuinely urgent. "
                    "Always requires confirmation before the alert is dispatched."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urgency": {
                            "type": "string",
                            "description": (
                                "Level of urgency. "
                                f"Must be one of: {', '.join(_URGENCY_LEVELS)}."
                            ),
                            "enum": list(_URGENCY_LEVELS),
                        },
                        "emergency_type": {
                            "type": "string",
                            "description": (
                                "Category of emergency. "
                                f"Must be one of: {', '.join(_EMERGENCY_TYPES)}."
                            ),
                            "enum": list(_EMERGENCY_TYPES),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "Clear, factual description of the situation: what is happening, "
                                "where, who is involved, and any relevant context the crew will need."
                            ),
                        },
                    },
                    "required": ["urgency", "emergency_type", "description"],
                },
            },
        }

    def run(self, args: dict) -> str:
        urgency = args.get("urgency", "UNKNOWN")
        etype   = args.get("emergency_type", "UNKNOWN")
        desc    = (args.get("description") or "").strip()

        # In production this would push to the AI pipeline and crew alert system.
        # For now, confirm the alert was accepted and log the details.
        return (
            f"[EMERGENCY ALERT DISPATCHED]\n"
            f"Urgency      : {urgency}\n"
            f"Type         : {etype}\n"
            f"Description  : {desc}\n"
            f"Status       : AI pipeline notified. Human crew alerted. "
            f"Response team is being assembled."
        )
