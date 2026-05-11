"""Talk to Claude with retrieved context."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from anthropic import Anthropic

from .store import Hit, VectorStore

DEFAULT_MODEL = "claude-sonnet-4-5"  # change if you have access to a different model
DEFAULT_MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are a careful assistant that answers questions using ONLY the snippets the user provides as CONTEXT.

Rules:
- If the context does not contain the answer, say so plainly. Do not invent facts.
- Cite the source filename in square brackets after each claim, e.g. [notes/algorithms.md].
  Multiple sources can be cited like [a.md][b.pdf].
- Keep answers concise. Quote directly when the wording matters.
"""


def _format_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        # Show just the filename, not the full path, to keep citations short.
        name = Path(h.source).name
        blocks.append(f"[{name}] (chunk {h.chunk_index})\n{h.text}")
    return "\n\n---\n\n".join(blocks)


@dataclass
class Answer:
    text: str
    hits: list[Hit]


class Chat:
    """Stateful chat that retrieves before each user turn."""

    def __init__(
        self,
        store: VectorStore,
        *,
        model: str = DEFAULT_MODEL,
        k: int = 5,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: str | None = None,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in your environment or a .env file."
            )
        self._client = Anthropic(api_key=key)
        self._store = store
        self._model = model
        self._k = k
        self._max_tokens = max_tokens
        self._history: list[dict] = []

    def ask(self, question: str) -> Answer:
        hits = self._store.query(question, k=self._k)
        context = _format_context(hits) if hits else "(no notes matched the question)"

        user_msg = (
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {question}"
        )
        # We don't send prior turns' full context blocks again — just the dialog.
        messages = self._history + [{"role": "user", "content": user_msg}]

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        # Anthropic returns a list of content blocks; concatenate text ones.
        text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        answer_text = "".join(text_parts).strip()

        # Save lightweight history (without context blocks) for follow-ups.
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer_text})

        return Answer(text=answer_text, hits=hits)

    def reset(self) -> None:
        self._history.clear()
