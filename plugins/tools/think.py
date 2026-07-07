"""Think tool — internal reasoning scratchpad.

The model calls this to externalise its reasoning before composing a reply.
The tool does nothing but return the text unchanged; the value is entirely in
forcing the model to articulate its logic in a committed, inspectable step
before it finalises an answer.

Use this for moderate complexity — situations where pausing to write out the
reasoning helps, but a full deep_think analytical pass is not needed.
"""
from __future__ import annotations

from src.interfaces import Tool


class ThinkTool(Tool):
    """Reasoning scratchpad — echoes the carry text back unchanged."""

    @property
    def name(self) -> str:
        return "think"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "think",
                "description": (
                    "Internal reasoning scratchpad. Write out your current thinking — "
                    "what you know, what is unclear, what tradeoffs exist — before "
                    "composing your final reply. The text is returned unchanged so you "
                    "can read it back and continue. Use this when you need a moment to "
                    "reason through something before answering, without invoking a full "
                    "analytical pass."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "carry_text": {
                            "type": "string",
                            "description": (
                                "Your in-progress reasoning: observations, open questions, "
                                "constraints, and tentative conclusions. Write freely — "
                                "this is for your eyes only before you reply."
                            ),
                        }
                    },
                    "required": ["carry_text"],
                },
            },
        }

    def run(self, args: dict) -> str:
        return args.get("carry_text", "")
