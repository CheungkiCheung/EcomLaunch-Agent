"""Thread-scoped Commerce context and idempotent upload intake contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commerce.api.data_service import CommerceDataService, DatasetNotFoundError
from app.commerce.chat.context import CommerceThreadContextService


def _service(tmp_path: Path) -> CommerceThreadContextService:
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-data")
    return CommerceThreadContextService(data_service=data_service)


def _write_orders(path: Path, *, order_id: str = "o1") -> None:
    path.write_text(
        f"order_id,order_purchase_timestamp\n{order_id},2018-01-01T00:00:00\n",
        encoding="utf-8",
    )


def test_workspace_identity_is_stable_and_scoped_by_user_and_thread(tmp_path: Path):
    service = _service(tmp_path)

    first = service.resolve(user_id="user-a", thread_id="thread-1")
    replay = service.resolve(user_id="user-a", thread_id="thread-1")
    other_thread = service.resolve(user_id="user-a", thread_id="thread-2")
    other_user = service.resolve(user_id="user-b", thread_id="thread-1")

    assert first == replay
    assert first.active_dataset_id is None
    assert first.workspace_id != other_thread.workspace_id
    assert first.workspace_id != other_user.workspace_id


def test_thread_upload_intake_is_content_idempotent_and_selects_active_dataset(
    tmp_path: Path,
):
    service = _service(tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _write_orders(uploads / "orders.csv")
    (uploads / "notes.txt").write_text("not a supported commerce table", encoding="utf-8")

    created = service.ingest_uploads(
        user_id="user-a",
        thread_id="thread-1",
        uploads_dir=uploads,
    )
    replayed = service.ingest_uploads(
        user_id="user-a",
        thread_id="thread-1",
        uploads_dir=uploads,
    )

    assert created.created is True
    assert created.replayed is False
    assert created.selected_filenames == ("orders.csv",)
    assert created.ignored_filenames == ("notes.txt",)
    assert created.context.active_dataset_id == created.view.manifest.dataset_id
    assert replayed.created is False
    assert replayed.replayed is True
    assert replayed.view.manifest.dataset_id == created.view.manifest.dataset_id
    assert len(service.list_datasets(user_id="user-a", thread_id="thread-1")) == 1


def test_changed_upload_bundle_creates_new_dataset_and_manual_selection_is_persisted(
    tmp_path: Path,
):
    service = _service(tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    orders = uploads / "orders.csv"
    _write_orders(orders, order_id="o1")
    first = service.ingest_uploads(
        user_id="user-a",
        thread_id="thread-1",
        uploads_dir=uploads,
    )

    _write_orders(orders, order_id="o2")
    second = service.ingest_uploads(
        user_id="user-a",
        thread_id="thread-1",
        uploads_dir=uploads,
    )

    assert second.created is True
    assert second.view.manifest.dataset_id != first.view.manifest.dataset_id
    assert second.context.active_dataset_id == second.view.manifest.dataset_id
    assert len(service.list_datasets(user_id="user-a", thread_id="thread-1")) == 2

    selected = service.select_dataset(
        user_id="user-a",
        thread_id="thread-1",
        dataset_id=first.view.manifest.dataset_id,
    )

    assert selected.active_dataset_id == first.view.manifest.dataset_id
    assert service.resolve(user_id="user-a", thread_id="thread-1") == selected


def test_dataset_selection_cannot_cross_thread_workspace_boundary(tmp_path: Path):
    service = _service(tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _write_orders(uploads / "orders.csv")
    created = service.ingest_uploads(
        user_id="user-a",
        thread_id="thread-1",
        uploads_dir=uploads,
    )

    with pytest.raises(DatasetNotFoundError):
        service.select_dataset(
            user_id="user-a",
            thread_id="thread-2",
            dataset_id=created.view.manifest.dataset_id,
        )


def test_explicit_file_selection_rejects_missing_or_path_like_names(tmp_path: Path):
    service = _service(tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _write_orders(uploads / "orders.csv")

    with pytest.raises(ValueError, match="plain filename"):
        service.ingest_uploads(
            user_id="user-a",
            thread_id="thread-1",
            uploads_dir=uploads,
            filenames=("../orders.csv",),
        )

    with pytest.raises(FileNotFoundError, match="missing.csv"):
        service.ingest_uploads(
            user_id="user-a",
            thread_id="thread-1",
            uploads_dir=uploads,
            filenames=("missing.csv",),
        )


def test_upload_intake_rejects_symbolic_links(tmp_path: Path):
    service = _service(tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "outside.csv"
    _write_orders(outside)
    (uploads / "orders.csv").symlink_to(outside)

    with pytest.raises(ValueError, match="symbolic link"):
        service.ingest_uploads(
            user_id="user-a",
            thread_id="thread-1",
            uploads_dir=uploads,
            filenames=("orders.csv",),
        )
