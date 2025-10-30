from typing import Optional, Type

def try_import_trust_evaluator() -> Optional[Type]:
    try:
        from munci.rumerapi.models.trust_evaluator import TrustEvaluator
        return TrustEvaluator
    except Exception:
        return None

def try_import_dart_verifier() -> Optional[Type]:
    try:
        from munci.opendart_tools.verifier import EnhancedDARTVerifier
        return EnhancedDARTVerifier
    except Exception:
        return None
