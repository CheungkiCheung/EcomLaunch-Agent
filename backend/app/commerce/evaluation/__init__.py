"""Evaluation gates and immutable audit contracts for Commerce Case Agent."""

from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    RealModelPreflightResult,
    run_real_model_preflight,
)

__all__ = [
    "PreflightStatus",
    "RealModelPreflightResult",
    "SEMANTIC_EVALUATOR_VERSION",
    "DeepSeekSemanticEvaluator",
    "SemanticEvaluationResult",
    "SemanticModelJudgment",
    "run_real_model_preflight",
]


def __getattr__(name: str):
    if name in {
        "SEMANTIC_EVALUATOR_VERSION",
        "DeepSeekSemanticEvaluator",
        "SemanticEvaluationResult",
        "SemanticModelJudgment",
    }:
        from app.commerce.evaluation import semantic

        return getattr(semantic, name)
    raise AttributeError(name)
