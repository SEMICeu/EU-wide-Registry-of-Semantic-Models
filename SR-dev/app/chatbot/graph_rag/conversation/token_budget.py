from __future__ import annotations

from dataclasses import dataclass

import tiktoken


def _encoding_name_for_model(model_name: str | None) -> str:
    if not model_name:
        return "cl100k_base"
    try:
        return tiktoken.encoding_for_model(model_name).name
    except KeyError:
        return "cl100k_base"


@dataclass(frozen=True)
class TokenBudget:
    max_context_tokens: int
    response_reserve_tokens: int

    @property
    def prompt_budget_tokens(self) -> int:
        return max(self.max_context_tokens - self.response_reserve_tokens, 0)


class TokenEstimator:
    def __init__(self, model_name: str | None) -> None:
        encoding_name = _encoding_name_for_model(model_name)
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count_text_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def trim_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        token_ids = self._encoding.encode(text)
        if len(token_ids) <= max_tokens:
            return text
        return self._encoding.decode(token_ids[:max_tokens])
