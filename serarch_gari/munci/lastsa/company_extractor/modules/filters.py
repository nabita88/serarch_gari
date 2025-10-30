from __future__ import annotations
import re
from typing import List, Tuple

# 그룹명 단독 사용 제외 설정
EXCLUDE_GROUPS = ["현대", "삼성", "LG", "SK"]
EXCLUDE_PARTICLES = ["에는", "는", "에서", "의", "에게", "에", "으로", "로", "만", "도"]


def should_exclude_group_mention(company: str, text: str) -> bool:

    if company not in EXCLUDE_GROUPS:
        return False

    particles_pattern = "|".join(map(re.escape, EXCLUDE_PARTICLES))
    pattern = rf'{re.escape(company)}(?:{particles_pattern})'
    return bool(re.search(pattern, text))
