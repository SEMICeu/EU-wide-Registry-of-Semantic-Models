from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chainlit as cl

from .token_budget import TokenEstimator


@dataclass
class ConversationTurn:
    role: str
    content: str
    rewritten_question: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    turns: List[ConversationTurn] = field(default_factory=list)
    summary: str = ""


class ConversationMemory:
    SESSION_KEY = "conversation_state"

    def __init__(
        self,
        token_estimator: TokenEstimator,
        recent_turns: int = 8,
        summary_token_budget: int = 350,
        history_token_budget: int = 1200,
    ) -> None:
        self._token_estimator = token_estimator
        self._recent_turns = recent_turns
        self._summary_token_budget = summary_token_budget
        self._history_token_budget = history_token_budget

    def init_state(self) -> None:
        cl.user_session.set(self.SESSION_KEY, ConversationState())

    def get_state(self) -> ConversationState:
        state = cl.user_session.get(self.SESSION_KEY)
        if isinstance(state, ConversationState):
            return state
        fresh = ConversationState()
        cl.user_session.set(self.SESSION_KEY, fresh)
        return fresh

    def save_state(self, state: ConversationState) -> None:
        cl.user_session.set(self.SESSION_KEY, state)

    def add_user_turn(self, content: str) -> None:
        state = self.get_state()
        state.turns.append(ConversationTurn(role="user", content=content))
        self._compact_history(state)
        self.save_state(state)

    def add_assistant_turn(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        state = self.get_state()
        state.turns.append(
            ConversationTurn(role="assistant", content=content, metadata=metadata or {})
        )
        self._compact_history(state)
        self.save_state(state)

    def set_last_user_rewrite(self, rewritten_question: str) -> None:
        state = self.get_state()
        for turn in reversed(state.turns):
            if turn.role == "user":
                turn.rewritten_question = rewritten_question
                break
        self.save_state(state)

    def build_context_for_prompt(self) -> str:
        state = self.get_state()
        summary_part = (
            self._token_estimator.trim_to_tokens(state.summary, self._summary_token_budget).strip()
        )
        history_part = self._render_recent_turns(state.turns)
        chunks = []
        if summary_part:
            chunks.append(f"Conversation summary:\n{summary_part}")
        if history_part:
            chunks.append(f"Recent turns:\n{history_part}")
        return "\n\n".join(chunks).strip()

    def _render_recent_turns(self, turns: List[ConversationTurn]) -> str:
        recent = turns[-self._recent_turns :]
        rendered_lines: List[str] = []
        for turn in recent:
            content = turn.content.strip()
            if not content:
                continue
            rendered_lines.append(f"{turn.role}: {content}")
            if turn.role == "user" and turn.rewritten_question:
                rendered_lines.append(f"resolved_user_question: {turn.rewritten_question}")
        text = "\n".join(rendered_lines)
        return self._token_estimator.trim_to_tokens(text, self._history_token_budget)

    def _compact_history(self, state: ConversationState) -> None:
        if len(state.turns) <= self._recent_turns:
            return

        older = state.turns[: -self._recent_turns]
        older_lines = []
        for turn in older:
            content = turn.content.strip()
            if content:
                older_lines.append(f"{turn.role}: {content}")
        if not older_lines:
            state.turns = state.turns[-self._recent_turns :]
            return

        combined = "\n".join(older_lines)
        previous_summary = state.summary.strip()
        new_summary_input = f"{previous_summary}\n{combined}".strip()
        state.summary = self._token_estimator.trim_to_tokens(
            new_summary_input, self._summary_token_budget
        )
        state.turns = state.turns[-self._recent_turns :]
