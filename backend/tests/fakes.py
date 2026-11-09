"""Scripted LLM used in tests: returns canned answers in order. NOT used by the app at runtime."""
from __future__ import annotations


class ScriptedLLM:
    def __init__(self, sql_answers: list[str], summary: str = "Scripted summary."):
        self.sql_answers = list(sql_answers)
        self.summary = summary
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        self.calls.append((system, user))
        if system.startswith("You write a short factual summary"):
            return self.summary
        if not self.sql_answers:
            raise RuntimeError("ScriptedLLM ran out of answers")
        return self.sql_answers.pop(0)
