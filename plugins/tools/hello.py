"""Mock greeting tool — demonstrates the Tool interface."""
from __future__ import annotations

from src.interfaces import Tool


class SayHelloTool(Tool):
    """Greets a person by name. Serves as a minimal MCP tool example."""

    @property
    def name(self) -> str:
        return "say_hello"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "say_hello",
                "description": "Greet someone by name and return a friendly greeting string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the person to greet.",
                        },
                    },
                    "required": ["name"],
                },
            },
        }

    def run(self, args: dict) -> str:
        name = args.get("name", "World")
        return f"Hello, {name}! 👋"
