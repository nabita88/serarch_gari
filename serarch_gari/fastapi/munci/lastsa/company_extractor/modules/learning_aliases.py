"""
학습 기능: 유사도 계산 결과를 별칭 사전에 자동 추가
"""
from typing import Dict, Optional
import json
import os
from . import utils


def _normalize_with_learning(extractor, company: str,
                             auto_learn: bool = False,
                             learn_threshold: float = 0.9) -> str:
    """학습 기능이 포함된 정규화"""
    # 1순위: alias_to_official에서 찾기
    if company in extractor.alias_to_official:
        return extractor.alias_to_official[company]

    # 2순위: company_master에 직접 존재
    if company in extractor.company_master:
        return company

    # 3순위: 유사도 기반 매칭 + 학습
    best_match = None
    best_similarity = 0

    for official in extractor.company_master.keys():
        similarity = utils._calculate_string_similarity(company, official)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = official

    # 임계값 이상이면 매칭
    if best_similarity >= learn_threshold and best_match:
        # 학습 기능: 사전에 자동 추가
        if auto_learn:
            _add_to_dictionary(extractor, company, best_match, best_similarity)

        return best_match

    return company


def _add_to_dictionary(extractor, alias: str, official: str, similarity: float):
    """새 별칭을 메모리 사전에 추가"""
    # 메모리에 추가
    extractor.alias_to_official[alias] = official

    # company_aliases에도 추가
    if official in extractor.company_aliases:
        if alias not in extractor.company_aliases[official]:
            extractor.company_aliases[official].append(alias)

    # 학습 이력 기록
    if not hasattr(extractor, 'learned_aliases'):
        extractor.learned_aliases = {}

    extractor.learned_aliases[alias] = {
        'official': official,
        'similarity': similarity,
        'method': 'similarity_matching'
    }

    print(f"[LEARN] '{alias}' → '{official}' (유사도: {similarity:.3f}) 사전에 추가됨")


def save_learned_aliases(extractor, output_path: Optional[str] = None):
    """학습된 별칭을 JSON 파일로 저장"""
    if not hasattr(extractor, 'learned_aliases') or not extractor.learned_aliases:
        print("[INFO] 학습된 별칭이 없습니다")
        return

    if output_path is None:
        output_path = os.path.join(extractor.DATA_PATH, "learned_aliases.json")

    # 기존 파일 로드 (있으면)
    existing = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass

    # 병합
    existing.update(extractor.learned_aliases)

    # 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(extractor.learned_aliases)}개 학습 별칭 저장: {output_path}")


def load_learned_aliases(extractor, input_path: Optional[str] = None):
    """저장된 학습 별칭 로드"""
    if input_path is None:
        input_path = os.path.join(extractor.DATA_PATH, "learned_aliases.json")

    if not os.path.exists(input_path):
        print(f"[INFO] 학습 파일 없음: {input_path}")
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            learned = json.load(f)

        # alias_to_official에 병합
        count = 0
        for alias, info in learned.items():
            official = info.get('official')
            if official and alias not in extractor.alias_to_official:
                extractor.alias_to_official[alias] = official
                count += 1

        print(f"[OK] {count}개 학습 별칭 로드: {input_path}")

    except Exception as e:
        print(f"[ERROR] 학습 파일 로드 실패: {e}")


def get_learning_stats(extractor) -> Dict:
    """학습 통계 반환"""
    if not hasattr(extractor, 'learned_aliases'):
        return {'total': 0, 'by_similarity': {}}

    stats = {
        'total': len(extractor.learned_aliases),
        'by_similarity': {}
    }

    # 유사도별 분류
    for alias, info in extractor.learned_aliases.items():
        sim = info.get('similarity', 0)
        range_key = f"{int(sim * 10) / 10:.1f}-{int(sim * 10) / 10 + 0.1:.1f}"

        if range_key not in stats['by_similarity']:
            stats['by_similarity'][range_key] = []

        stats['by_similarity'][range_key].append({
            'alias': alias,
            'official': info.get('official'),
            'similarity': sim
        })

    return stats
