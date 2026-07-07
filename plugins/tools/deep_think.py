"""Deep Think tool — delegates a complex question to an extended reasoning pass.

The model calls this tool when a problem benefits from careful multi-step
reasoning before a reply is composed.  The tool runs a separate LLM completion
with Gemini's native thinking budget enabled, then returns the synthesized
conclusion for the agent to use in its response.
"""
from __future__ import annotations

from pathlib import Path

from src.interfaces import Tool

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.toml"

_REASONING_PROMPT = """\
You are a precise analytical reasoner. Carefully work through the problem below,
considering all relevant constraints, tradeoffs, and edge cases. Then return only
your final synthesized answer — clear, direct, and actionable. Do not include
meta-commentary about your reasoning process.

Problem:
{problem}
"""


class DeepThinkTool(Tool):
    """Performs extended chain-of-thought reasoning on a complex question."""

    @property
    def name(self) -> str:
        return "deep_think"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "deep_think",
                "description": (
                    "Performs extended reasoning on a complex question, ambiguous situation, "
                    "or multi-step decision before answering. Use this when the question "
                    "requires careful tradeoff analysis, synthesizing several facts, or "
                    "working through logic that benefits from a dedicated thinking pass. "
                    "Returns a well-reasoned, actionable conclusion."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "problem": {
                            "type": "string",
                            "description": (
                                "The question, scenario, or decision to reason through carefully. "
                                "Be specific — include all relevant context the reasoner will need."
                            ),
                        }
                    },
                    "required": ["problem"],
                },
            },
        }

    def run(self, args: dict) -> str:
        problem = (args.get("problem") or "").strip()
        if not problem:
            return "[error] No problem provided to deep_think."

        from src.config import Config
        from src.llm import LLMClient

        cfg = Config.load(_CONFIG_PATH)
        llm = LLMClient(cfg)
        prompt = _REASONING_PROMPT.format(problem=problem)
        return llm.think(prompt)
