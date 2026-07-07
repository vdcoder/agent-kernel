"""LLM client."""
from __future__ import annotations

from openai import OpenAI

from src.config import Config


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BASE = """\
You are a customer service assistant helping cruise passengers with their inquiries and goals.

Guidelines:
- Be concise and clear in your responses.
- Avoid repeating information already provided in the conversation.
- Always provide accurate and helpful information.
- Be polite and professional in your tone.
- Never invent citations.

Citations:
- Whenever you state a fact about rules, prices, policies, hours, or procedures, cite the knowledge base source inline using a numbered marker such as [1].
- When several consecutive items (e.g. a bullet list) all come from the same source, place a single citation at the end of the last item rather than repeating it on every line.
- At the end of your response, include a "---" divider followed by a numbered reference list.
- Each reference must include the original PDF file name (found in <!-- BEGIN FILE: ... --> comments) and the section title (e.g. the nearest ## heading) where the information came from.
- Example format:
    > The corkage fee is $15 per bottle [1].
    > ---
    > [1] 08_billing_agent_kb.pdf — § Beverage & Corkage Fees
- Only add the reference section when at least one citation is present. Do not add it for purely conversational replies.
- If the same source is cited multiple times, use the same number throughout.

Tool errors:
- If a tool returns a result that starts with [error], explain what went wrong in plain language.
- Suggest the most likely cause based on the arguments that were passed.
- Offer a concrete next step (e.g. correct the input, try a different option, or contact support).\
"""


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = OpenAI(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
        )

    def health_check(self) -> bool:
        """Return True if the endpoint is reachable."""
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    def chat(self, messages: list[dict], system: str = "", tool_schemas: list[dict] | None = None) -> object:
        """Send a chat completion request.

        *system* is prepended as a system message when provided.
        *tool_schemas* is the list of OpenAI-format tool dicts to expose;
        pass an empty list or omit to disable tool calling entirely.
        """
        # Guard: Gemini rejects tool-role messages with an empty/missing name.
        # Strip them here as the last line of defence before the wire call.
        safe_messages = [
            m for m in messages
            if not (m.get("role") == "tool" and not m.get("name"))
        ]

        full_messages = (
            [{"role": "system", "content": system}] if system else []
        ) + safe_messages

        extra: dict = {}
        if self.config.llm.local_chat_kvslot >= 0:
            extra = {
                "id_slot": self.config.llm.local_chat_kvslot,
                "cache_prompt": True,
            }

        kwargs: dict = dict(
            model=self.config.llm.model,
            messages=full_messages,
            max_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
            extra_body=extra or None,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        return self._client.chat.completions.create(**kwargs)

    def complete(self, prompt: str, max_tokens: int = None, temperature: float = None, kvslot: int = -1) -> str:
        """Simple single-turn completion without tools — used for summarisation."""
        extra: dict = {}
        if kvslot >= 0:
            extra = {
                "id_slot": kvslot,
                "cache_prompt": True,
            }

        resp = self._client.chat.completions.create(
            model=self.config.llm.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens if max_tokens is not None else self.config.llm.max_tokens,
            temperature=temperature if temperature is not None else self.config.llm.temperature,
            extra_body=extra or None,
        )
        content = resp.choices[0].message.content
        return (content or "").strip()

    def think(self, prompt: str, thinking_budget: int = 8000) -> str:
        """Run a single-turn completion with the model's extended reasoning enabled.

        Uses Gemini's thinking_config (thinking_budget tokens of private scratchpad).
        Temperature is forced to 1, which Gemini requires when thinking is active.
        Falls back to a plain complete() call if the endpoint rejects the extra field.
        """
        try:
            resp = self._client.chat.completions.create(
                model=self.config.llm.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.llm.max_tokens,
                temperature=1,
                extra_body={"thinking_config": {"thinking_budget": thinking_budget}},
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            # Endpoint does not support thinking_config — fall back gracefully.
            return self.complete(prompt, temperature=0.3)

    def embed(self, text: str) -> list[float]:
        """Return a 3072-dim embedding vector for *text* using gemini-embedding-001."""
        resp = self._client.embeddings.create(
            model="models/gemini-embedding-001",
            input=text,
        )
        return resp.data[0].embedding
