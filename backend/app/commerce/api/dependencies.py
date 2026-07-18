"""FastAPI dependencies for the feature-flagged Commerce API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Header, HTTPException

from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.service import CommerceReadService
from app.commerce.domain.ids import WorkspaceId
from deerflow.persistence.engine import get_session_factory


def get_commerce_read_service() -> CommerceReadService:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="Commerce persistence is not initialized",
        )
    return CommerceReadService(session_factory)


def get_commerce_data_service() -> CommerceDataService:
    storage_root = Path(
        os.getenv("COMMERCE_STORAGE_ROOT", ".deer-flow/commerce/data")
    )
    return CommerceDataService(storage_root=storage_root)


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
