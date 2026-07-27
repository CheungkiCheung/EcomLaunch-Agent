"""Durable Thread-to-Commerce workspace and active Dataset context."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from app.commerce.api.data_service import CommerceDataService, DatasetView
from app.commerce.data.intake import DataIntakeError
from app.commerce.domain.ids import DatasetId, WorkspaceId
from app.commerce.domain.models import CommerceModel


class ThreadContextIntegrityError(ValueError):
    """Persisted Thread context or intake receipt is invalid or mismatched."""


class UploadDigest(CommerceModel):
    filename: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CommerceThreadContext(CommerceModel):
    schema_version: str = "commerce.thread-context@1.0.0"
    workspace_id: WorkspaceId
    user_scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    thread_scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_dataset_id: DatasetId | None = None
    active_upload_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    revision: int = Field(default=0, ge=0)
    updated_at: datetime | None = None


class ThreadUploadReceipt(CommerceModel):
    schema_version: str = "commerce.thread-upload-receipt@1.0.0"
    workspace_id: WorkspaceId
    dataset_id: DatasetId
    upload_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: tuple[UploadDigest, ...] = Field(min_length=1)
    created_at: datetime


class ThreadUploadIngestionResult(CommerceModel):
    context: CommerceThreadContext
    view: DatasetView
    selected_filenames: tuple[str, ...]
    ignored_filenames: tuple[str, ...]
    upload_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created: bool
    replayed: bool


class CommerceThreadContextService:
    """Map one authenticated Chat thread to isolated Commerce data state."""

    SUPPORTED_SUFFIXES = frozenset({".csv", ".json", ".jsonl", ".xlsx", ".zip"})
    COPY_CHUNK_BYTES = 1024 * 1024

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        context_root: Path | None = None,
    ) -> None:
        self._data = data_service
        self._context_root = context_root or data_service.storage_root / "_thread_contexts"

    @property
    def data_service(self) -> CommerceDataService:
        return self._data

    def resolve(self, *, user_id: str, thread_id: str) -> CommerceThreadContext:
        user_id, thread_id = self._validate_scope(user_id, thread_id)
        expected = self._new_context(user_id=user_id, thread_id=thread_id)
        path = self._context_path(expected.workspace_id)
        if not path.exists():
            return expected
        persisted = self._load_model(path, CommerceThreadContext)
        if persisted.workspace_id != expected.workspace_id or persisted.user_scope_sha256 != expected.user_scope_sha256 or persisted.thread_scope_sha256 != expected.thread_scope_sha256:
            raise ThreadContextIntegrityError("Persisted Commerce Thread context does not match the current user/thread")
        if persisted.active_dataset_id is not None:
            self._data.get_view(persisted.workspace_id, persisted.active_dataset_id)
        return persisted

    def ingest_uploads(
        self,
        *,
        user_id: str,
        thread_id: str,
        uploads_dir: Path,
        filenames: tuple[str, ...] | None = None,
    ) -> ThreadUploadIngestionResult:
        context = self.resolve(user_id=user_id, thread_id=thread_id)
        selected, ignored = self._select_upload_paths(Path(uploads_dir), filenames)

        self._data.storage_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="commerce-thread-upload-",
            dir=self._data.storage_root,
        ) as temporary_dir:
            snapshots, digests = self._snapshot_uploads(
                selected,
                destination=Path(temporary_dir),
            )
            fingerprint = self._upload_fingerprint(digests)
            receipt_path = self._receipt_path(context.workspace_id, fingerprint)
            if receipt_path.exists():
                receipt = self._load_receipt(
                    receipt_path,
                    workspace_id=context.workspace_id,
                    fingerprint=fingerprint,
                    digests=digests,
                )
                view = self._data.get_view(context.workspace_id, receipt.dataset_id)
                active = self._activate(
                    context,
                    dataset_id=receipt.dataset_id,
                    upload_fingerprint=fingerprint,
                )
                return ThreadUploadIngestionResult(
                    context=active,
                    view=view,
                    selected_filenames=tuple(item.filename for item in digests),
                    ignored_filenames=ignored,
                    upload_fingerprint=fingerprint,
                    created=False,
                    replayed=True,
                )

            view = self._data.ingest_paths(context.workspace_id, snapshots)
            candidate = ThreadUploadReceipt(
                workspace_id=context.workspace_id,
                dataset_id=view.manifest.dataset_id,
                upload_fingerprint=fingerprint,
                files=digests,
                created_at=datetime.now(UTC),
            )
            created = self._write_receipt_exclusive(receipt_path, candidate)
            receipt = (
                candidate
                if created
                else self._load_receipt(
                    receipt_path,
                    workspace_id=context.workspace_id,
                    fingerprint=fingerprint,
                    digests=digests,
                )
            )
            if not created:
                view = self._data.get_view(context.workspace_id, receipt.dataset_id)

            active = self._activate(
                context,
                dataset_id=receipt.dataset_id,
                upload_fingerprint=fingerprint,
            )
            return ThreadUploadIngestionResult(
                context=active,
                view=view,
                selected_filenames=tuple(item.filename for item in digests),
                ignored_filenames=ignored,
                upload_fingerprint=fingerprint,
                created=created,
                replayed=not created,
            )

    def list_datasets(
        self,
        *,
        user_id: str,
        thread_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[DatasetView, ...]:
        context = self.resolve(user_id=user_id, thread_id=thread_id)
        return self._data.list_views(context.workspace_id, limit=limit, offset=offset)

    def select_dataset(
        self,
        *,
        user_id: str,
        thread_id: str,
        dataset_id: DatasetId,
    ) -> CommerceThreadContext:
        context = self.resolve(user_id=user_id, thread_id=thread_id)
        self._data.get_view(context.workspace_id, dataset_id)
        return self._activate(
            context,
            dataset_id=dataset_id,
            upload_fingerprint=self._fingerprint_for_dataset(
                context.workspace_id,
                dataset_id,
            ),
        )

    @staticmethod
    def workspace_id_for(*, user_id: str, thread_id: str) -> WorkspaceId:
        user_id, thread_id = CommerceThreadContextService._validate_scope(user_id, thread_id)
        seed = json.dumps(
            {
                "schema": "commerce-thread-workspace@1.0.0",
                "thread_id": thread_id,
                "user_id": user_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return WorkspaceId(f"wsp_{uuid5(NAMESPACE_URL, seed).hex}")

    def _new_context(self, *, user_id: str, thread_id: str) -> CommerceThreadContext:
        return CommerceThreadContext(
            workspace_id=self.workspace_id_for(user_id=user_id, thread_id=thread_id),
            user_scope_sha256=self._scope_sha256("user", user_id),
            thread_scope_sha256=self._scope_sha256("thread", thread_id),
        )

    def _activate(
        self,
        context: CommerceThreadContext,
        *,
        dataset_id: DatasetId,
        upload_fingerprint: str | None,
    ) -> CommerceThreadContext:
        if context.active_dataset_id == dataset_id and context.active_upload_fingerprint == upload_fingerprint:
            return context
        updated = context.model_copy(
            update={
                "active_dataset_id": dataset_id,
                "active_upload_fingerprint": upload_fingerprint,
                "revision": context.revision + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        self._write_model_atomic(self._context_path(context.workspace_id), updated)
        return updated

    def _select_upload_paths(
        self,
        uploads_dir: Path,
        filenames: tuple[str, ...] | None,
    ) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        if uploads_dir.is_symlink():
            raise ValueError("Commerce uploads directory cannot be a symbolic link")
        if not uploads_dir.is_dir():
            raise FileNotFoundError(f"Commerce uploads directory does not exist: {uploads_dir}")

        ignored: list[str] = []
        if filenames is None:
            selected: list[Path] = []
            for entry in sorted(uploads_dir.iterdir(), key=lambda item: item.name):
                if entry.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                    if entry.is_file() or entry.is_symlink():
                        ignored.append(entry.name)
                    continue
                selected.append(entry)
        else:
            if len(filenames) != len(set(filenames)):
                raise ValueError("Commerce upload filenames must be unique")
            selected = []
            for filename in filenames:
                if Path(filename).name != filename or filename in {".", ".."} or "\\" in filename:
                    raise ValueError("Commerce uploads require a plain filename")
                path = uploads_dir / filename
                if not path.exists() and not path.is_symlink():
                    raise FileNotFoundError(f"Uploaded file does not exist: {filename}")
                if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                    raise DataIntakeError(f"Unsupported Commerce upload format: {filename}")
                selected.append(path)

        if not selected:
            raise DataIntakeError("No supported Commerce data files were found; upload CSV, JSON, JSONL, XLSX, or ZIP")
        for path in selected:
            if path.is_symlink():
                raise ValueError(f"Commerce upload cannot be a symbolic link: {path.name}")
            if not path.is_file():
                raise ValueError(f"Commerce upload is not a regular file: {path.name}")
        return tuple(selected), tuple(ignored)

    def _snapshot_uploads(
        self,
        source_paths: tuple[Path, ...],
        *,
        destination: Path,
    ) -> tuple[tuple[Path, ...], tuple[UploadDigest, ...]]:
        snapshots: list[Path] = []
        digests: list[UploadDigest] = []
        for source in source_paths:
            target = destination / source.name
            digest = hashlib.sha256()
            total = 0
            with self._open_regular_no_follow(source) as reader, target.open("xb") as writer:
                while chunk := reader.read(self.COPY_CHUNK_BYTES):
                    total += len(chunk)
                    if total > self._data.MAX_UPLOAD_BYTES:
                        raise DataIntakeError(f"Uploaded file exceeds size limit: {source.name}")
                    digest.update(chunk)
                    writer.write(chunk)
            snapshots.append(target)
            digests.append(
                UploadDigest(
                    filename=source.name,
                    size_bytes=total,
                    sha256=digest.hexdigest(),
                )
            )
        ordered = tuple(sorted(digests, key=lambda item: item.filename))
        snapshots_by_name = {path.name: path for path in snapshots}
        return tuple(snapshots_by_name[item.filename] for item in ordered), ordered

    @staticmethod
    def _open_regular_no_follow(path: Path) -> BinaryIO:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise ValueError(f"Commerce upload cannot be opened safely: {path.name}") from exc
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError(f"Commerce upload is not a regular file: {path.name}")
            return os.fdopen(fd, "rb")
        except Exception:
            os.close(fd)
            raise

    @staticmethod
    def _upload_fingerprint(files: tuple[UploadDigest, ...]) -> str:
        payload = [item.model_dump(mode="json") for item in files]
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

    def _fingerprint_for_dataset(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
    ) -> str | None:
        receipts_root = self._workspace_context_root(workspace_id) / "ingestions"
        if not receipts_root.is_dir() or receipts_root.is_symlink():
            return None
        for path in sorted(receipts_root.glob("*.json")):
            receipt = self._load_model(path, ThreadUploadReceipt)
            if receipt.workspace_id == workspace_id and receipt.dataset_id == dataset_id:
                return receipt.upload_fingerprint
        return None

    def _load_receipt(
        self,
        path: Path,
        *,
        workspace_id: WorkspaceId,
        fingerprint: str,
        digests: tuple[UploadDigest, ...],
    ) -> ThreadUploadReceipt:
        receipt = self._load_model(path, ThreadUploadReceipt)
        if receipt.workspace_id != workspace_id or receipt.upload_fingerprint != fingerprint or receipt.files != digests:
            raise ThreadContextIntegrityError("Persisted Commerce upload receipt does not match the current bundle")
        return receipt

    def _write_receipt_exclusive(
        self,
        path: Path,
        receipt: ThreadUploadReceipt,
    ) -> bool:
        self._ensure_private_directory(path.parent)
        if path.is_symlink():
            raise ThreadContextIntegrityError("Commerce upload receipt cannot be a symbolic link")
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(
                    receipt.model_dump(mode="json"),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            return True
        except FileExistsError:
            return False

    def _write_model_atomic(self, path: Path, model: CommerceModel) -> None:
        self._ensure_private_directory(path.parent)
        if path.is_symlink():
            raise ThreadContextIntegrityError("Commerce Thread context cannot be a symbolic link")
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    model.model_dump(mode="json"),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _load_model(path: Path, model_type):
        if path.is_symlink():
            raise ThreadContextIntegrityError(f"Persisted Commerce state is a symbolic link: {path}")
        if not path.is_file():
            raise ThreadContextIntegrityError(f"Persisted Commerce state is missing: {path}")
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ThreadContextIntegrityError(f"Persisted Commerce state is invalid: {path}") from exc

    @staticmethod
    def _validate_scope(user_id: str, thread_id: str) -> tuple[str, str]:
        normalized_user = str(user_id).strip()
        normalized_thread = str(thread_id).strip()
        if not normalized_user or not normalized_thread:
            raise ValueError("Commerce Thread context requires user_id and thread_id")
        return normalized_user, normalized_thread

    @staticmethod
    def _scope_sha256(kind: str, value: str) -> str:
        return hashlib.sha256(f"commerce:{kind}@1.0.0\0{value}".encode()).hexdigest()

    def _workspace_context_root(self, workspace_id: WorkspaceId) -> Path:
        return self._context_root / str(workspace_id)

    def _context_path(self, workspace_id: WorkspaceId) -> Path:
        return self._workspace_context_root(workspace_id) / "context.json"

    def _receipt_path(self, workspace_id: WorkspaceId, fingerprint: str) -> Path:
        return self._workspace_context_root(workspace_id) / "ingestions" / f"{fingerprint}.json"

    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        current = path
        while True:
            if current.is_symlink():
                raise ThreadContextIntegrityError(f"Commerce context directory cannot be a symbolic link: {current}")
            if current.parent == current:
                break
            current = current.parent
