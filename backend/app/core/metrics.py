"""Prometheus metrics shared across the API and assistant."""

from prometheus_client import Counter

ASSISTANT_TURNS = Counter(
    "sentinelbank_assistant_turns_total",
    "Assistant turns, by how they ended",
    ["outcome"],
)

ASSISTANT_DECISIONS = Counter(
    "sentinelbank_assistant_decisions_total",
    "Analyst decisions on actions the assistant proposed",
    ["tool", "decision"],
)
