from __future__ import annotations
from typing import List
from dataclasses import dataclass

@dataclass
class UnifiedEventResult:
    labels: List[str]
    event_phrases: List[str]
    confidence: float
    source: str  # "hyperclova", "chatgpt", "both", "none"
    raw_response: str = ""
