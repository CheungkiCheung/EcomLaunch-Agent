"""FastAPI dependencies for the feature-flagged Commerce API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Header, HTTPException

from app.commerce.actions.execution import ActionExecutionService
from app.commerce.actions.follow_up import FollowUpService
from app.commerce.api.action_service import CommerceActionService
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_reconciliation_service import CommerceRunReconciliationService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.api.service import CommerceReadService
from app.commerce.api.skill_candidate_service import CommerceSkillCandidateService
from app.commerce.data.semantic_candidate_service import SemanticCandidateService
from app.commerce.domain.ids import WorkspaceId
from deerflow.persistence.engine import get_session_factory


def get_commerce_read_service() -> CommerceReadService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceReadService(
        session_factory,
        data_service=get_commerce_data_service(),
    )


def get_commerce_run_service() -> CommerceRunService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceRunService(session_factory)


def get_commerce_run_reconciliation_service() -> CommerceRunReconciliationService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceRunReconciliationService(session_factory)


def get_commerce_action_service() -> CommerceActionService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceActionService(
        session_factory,
        data_service=get_commerce_data_service(),
    )


def get_commerce_action_execution_service() -> ActionExecutionService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    storage_root = Path(
        os.getenv(
            "COMMERCE_ACTION_STORAGE_ROOT",
            ".deer-flow/commerce/action-artifacts",
        )
    )
    return ActionExecutionService(
        session_factory,
        storage_root=storage_root,
    )


def get_commerce_follow_up_service() -> FollowUpService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return FollowUpService(
        session_factory,
        data_service=get_commerce_data_service(),
    )


def get_commerce_data_service() -> CommerceDataService:
    storage_root = Path(os.getenv("COMMERCE_STORAGE_ROOT", ".deer-flow/commerce/data"))
    return CommerceDataService(storage_root=storage_root)


def get_commerce_semantic_candidate_service() -> SemanticCandidateService:
    return SemanticCandidateService()


def get_commerce_skill_candidate_service() -> CommerceSkillCandidateService:
    return CommerceSkillCandidateService(
        experiment_root=Path(
            os.getenv(
                "COMMERCE_EXPERIMENT_ROOT",
                ".deer-flow/commerce/evaluation/experiments",
            )
        ),
        skill_root=Path(
            os.getenv(
                "COMMERCE_SKILL_ROOT",
                ".deer-flow/commerce/evaluation/skills",
            )
        ),
    )


def get_commerce_analysis_service() -> CommerceAnalysisService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceAnalysisService(
        data_service=get_commerce_data_service(),
        session_factory=session_factory,
    )


def get_commerce_workspace_id(
    raw_workspace_id: Annotated[
        str,
        Header(alias="X-Commerce-Workspace-Id"),
    ],
) -> WorkspaceId:
    try:
        return WorkspaceId(raw_workspace_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="X-Commerce-Workspace-Id must be a valid WorkspaceId",
        ) from exc


def get_commerce_actor_id(
    raw_actor_id: Annotated[
        str,
        Header(alias="X-Commerce-Actor-Id", min_length=1, max_length=128),
    ],
) -> str:
    actor_id = raw_actor_id.strip()
    if not actor_id:
        raise HTTPException(
            status_code=400,
            detail="X-Commerce-Actor-Id cannot be blank",
        )
    return actor_id
