"""Rolling conversation summariser."""
from __future__ import annotations

from src.llm import LLMClient

_CONV_PROMPT = """\
Summarize the following conversation between a cruise guest and their onboard assistant.
Capture: topics discussed, requests made, information given, open questions.
Be concise. Output only the summary text (no preamble)."""

_ROLLING_PROMPT_TEMPLATE = """\
You are maintaining a rolling prose summary of a conversation between a cruise guest and their onboard assistant.
One exchange is aging out of the verbatim window and must be folded into the existing summary.

Guidelines:
- Decide what is genuinely useful and worth remembering — keep it, even if it is older.
- If the new exchange adds something important, weave it in naturally.
- If the new exchange is routine or already captured, it is perfectly fine to leave the summary nearly unchanged.
- Compress by merging overlapping points and dropping low-value details, not by blindly cutting the oldest text.
- You do NOT need to fill the limit — staying well under {max_chars} characters is ideal as long as all important information is preserved. Equally, if the conversation is rich and detailed, it is perfectly fine to use the available budget to do it justice.
- If you must choose what to drop, prefer dropping minor pleasantries or repetitive exchanges over substantive facts about the guest's requests or the assistant's answers.
- Output only the updated summary text (no preamble)."""


class Summarizer:
    """Produces rolling conversation summaries."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def summarize_conversation(
        self,
        exchanges: list[dict],
        existing_summary: str = "",
        max_tokens: int | None = None,
        summary_max_chars: int = 2500,
    ) -> str:
        """Fold evicted *exchanges* into *existing_summary* and return the updated text.

        ``max_tokens`` defaults to None so ``complete()`` uses the model's
        configured limit.  Gemini Flash consumes thinking tokens from the same
        budget, so a hard cap of 600 would leave too little room for output.
        ``summary_max_chars`` is passed into the rolling prompt so the model
        self-compresses before the emergency trim ever fires.
        """
        turns_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in exchanges
            if isinstance(m.get("content"), str) and m.get("content", "").strip()
        )
        if existing_summary:
            rolling_prompt = _ROLLING_PROMPT_TEMPLATE.format(max_chars=summary_max_chars)
            prompt = (
                f"{rolling_prompt}\n\n"
                f"### Existing Summary\n{existing_summary}\n\n"
                f"### New Conversation Turns\n{turns_text}"
            )
        else:
            prompt = f"{_CONV_PROMPT}\n\n{turns_text}"
        return self._llm.complete(prompt, max_tokens=max_tokens)

