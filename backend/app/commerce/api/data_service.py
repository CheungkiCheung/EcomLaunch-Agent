"""File-backed deterministic dataset application service."""

from __future__ import annotations

import hashlib
import json
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

from app.commerce.data.capabilities import CapabilityProfile, CapabilityRegistry
from app.commerce.data.intake import (
    DataBundleManifest,
    DataIntakeError,
    DataIntakeService,
    DatasetIntegrityError,
)
from app.commerce.data.normalized import NormalizedDataset, OlistAdapter
from app.commerce.data.profiler import DataProfiler, DatasetProfile
from app.commerce.data.semantic_mapper import (
    SemanticConfirmation,
    SemanticField,
    SemanticMapper,
    SemanticMappingProfile,
    WorkspaceSemanticStore,
)
from app.commerce.domain.ids import DatasetId, WorkspaceId
from app.commerce.domain.models import CommerceModel


class DatasetNotFoundError(LookupError):
    """The requested Dataset does not exist in the requested Workspace."""


class MappingResumeConflictError(ValueError):
    """A mapping-resume command conflicts with an immutable prior receipt."""


@dataclass(frozen=True)
class DatasetView:
    manifest: DataBundleManifest
    profile: DatasetProfile
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile


class MappingResumeReceipt(CommerceModel):
    schema_version: str = "commerce.mapping-resume-receipt@1.0.0"
    request_sha256: str
    actor_id: str
    confirmations: tuple[SemanticConfirmation, ...]
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile


@dataclass(frozen=True)
class MappingResumeResult:
    confirmations: tuple[SemanticConfirmation, ...]
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile
    created: bool
    replayed: bool


class CommerceDataService:
    """Own safe uploads and deterministic Dataset views without an LLM."""

    MAX_UPLOAD_BYTES = 200 * 1024 * 1024

    def __init__(self, *, storage_root: Path) -> None:
        self._storage_root = storage_root
        self._intake = DataIntakeService(storage_root=storage_root)
        self._profiler = DataProfiler(storage_root=storage_root)
        self._semantic_store = WorkspaceSemanticStore(storage_root=storage_root)
        self._mapper = SemanticMapper(semantic_store=self._semantic_store)
        self._capabilities = CapabilityRegistry()

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def ingest_uploads(
        self,
        workspace_id: WorkspaceId,
        uploads: tuple[tuple[str, bytes], ...],
    ) -> DatasetView:
        if not uploads:
            raise DataIntakeError("At least one uploaded file is required")
        self._storage_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="commerce-upload-",
            dir=self._storage_root,
        ) as temporary_dir:
            source_paths: list[Path] = []
            for filename, content in uploads:
                self._validate_filename(filename)
                if len(content) > self.MAX_UPLOAD_BYTES:
                    raise DataIntakeError(f"Uploaded file exceeds size limit: {filename}")
                path = Path(temporary_dir) / filename
                path.write_bytes(content)
                source_paths.append(path)
            manifest = self._intake.ingest(workspace_id, tuple(source_paths))
        return self._build_view(manifest)

    def ingest_paths(
        self,
        workspace_id: WorkspaceId,
        source_paths: tuple[Path, ...],
    ) -> DatasetView:
        """Ingest already-snapshotted regular files without loading them into memory.

        Callers are responsible for copying untrusted inputs into a private
        temporary directory first.  This method still rejects symbolic links,
        non-files, duplicate names, and files above the Commerce intake limit.
        """

        if not source_paths:
            raise DataIntakeError("At least one uploaded file is required")
        names: set[str] = set()
        validated: list[Path] = []
        for source_path in source_paths:
            path = Path(source_path)
            self._validate_filename(path.name)
            if path.name in names:
                raise DataIntakeError(f"Duplicate upload filename: {path.name}")
            names.add(path.name)
            if path.is_symlink():
                raise DataIntakeError(f"Uploaded symbolic links are not allowed: {path.name}")
            if not path.is_file():
                raise DataIntakeError(f"Uploaded file does not exist: {path.name}")
            if path.stat().st_size > self.MAX_UPLOAD_BYTES:
                raise DataIntakeError(f"Uploaded file exceeds size limit: {path.name}")
            validated.append(path)

        self._storage_root.mkdir(parents=True, exist_ok=True)
        manifest = self._intake.ingest(workspace_id, tuple(validated))
        return self._build_view(manifest)

    def get_view(self, workspace_id: WorkspaceId, dataset_id: DatasetId) -> DatasetView:
        manifest_path = self._storage_root / str(workspace_id) / str(dataset_id) / "manifest.json"
        if not manifest_path.is_file():
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
        if manifest_path.is_symlink():
            raise DatasetIntegrityError(f"Stored Dataset manifest is a symbolic link: {dataset_id}")
        try:
            manifest = DataBundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DatasetIntegrityError(f"Stored Dataset manifest is invalid: {dataset_id}") from exc
        if manifest.workspace_id != workspace_id or manifest.dataset_id != dataset_id:
            raise DatasetIntegrityError(f"Stored Dataset manifest identity does not match its request: {dataset_id}")
        self._intake.verify_manifest(manifest)
        try:
            return self._build_view(manifest)
        except DatasetIntegrityError:
            raise
        except Exception as exc:
            raise DatasetIntegrityError(f"Stored Dataset data cannot be profiled: {dataset_id}") from exc

    def list_views(
        self,
        workspace_id: WorkspaceId,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[DatasetView, ...]:
        """Return verified Dataset views for one Workspace in stable newest-first order."""

        if limit < 1 or offset < 0:
            raise ValueError("Dataset list limit must be positive and offset cannot be negative")
        workspace_root = self._storage_root / str(workspace_id)
        if not workspace_root.is_dir() or workspace_root.is_symlink():
            return ()

        candidates: list[tuple[object, DatasetId]] = []
        for entry in workspace_root.iterdir():
            if not entry.is_dir() or entry.is_symlink() or not entry.name.startswith("dset_"):
                continue
            try:
                dataset_id = DatasetId(entry.name)
            except ValueError:
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            try:
                manifest = DataBundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise DatasetIntegrityError(f"Stored Dataset manifest is invalid: {dataset_id}") from exc
            if manifest.workspace_id != workspace_id or manifest.dataset_id != dataset_id:
                raise DatasetIntegrityError(f"Stored Dataset manifest identity does not match its path: {dataset_id}")
            candidates.append((self._sort_timestamp(manifest.created_at), dataset_id))

        candidates.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
        return tuple(self.get_view(workspace_id, dataset_id) for _, dataset_id in candidates[offset : offset + limit])

    def semantic_confirmations(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
    ) -> tuple[SemanticConfirmation, ...]:
        view = self.get_view(workspace_id, dataset_id)
        try:
            confirmations = self._semantic_store.load(
                workspace_id,
                dataset_id=dataset_id,
            )
        except Exception as exc:
            raise DatasetIntegrityError(f"Stored semantic confirmations are invalid: {dataset_id}") from exc
        columns = {(table.table_name, column.name) for table in view.profile.tables for column in table.columns}
        return tuple(
            sorted(
                (confirmation for key, confirmation in confirmations.items() if key in columns),
                key=lambda item: (item.table_name, item.column_name),
            )
        )

    def normalize(self, workspace_id: WorkspaceId, dataset_id: DatasetId) -> NormalizedDataset:
        view = self.get_view(workspace_id, dataset_id)
        return OlistAdapter(storage_root=self._storage_root).normalize(
            view.manifest,
            view.mappings,
        )

    def write_derived_artifact(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        filename: str,
        payload: dict,
    ) -> Path:
        if Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError("Derived artifact filename must be a plain file name")
        root = self._storage_root / str(workspace_id) / str(dataset_id) / "derived"
        root.mkdir(parents=True, exist_ok=True)
        path = root / filename
        if not path.exists():
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        return path

    def confirm_mapping(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        table_name: str,
        column_name: str,
        semantic_field: SemanticField,
    ) -> SemanticConfirmation:
        view = self.get_view(workspace_id, dataset_id)
        try:
            view.profile.table(table_name).column(column_name)
        except KeyError as exc:
            raise DataIntakeError(f"Unknown Dataset column: {table_name}.{column_name}") from exc
        return self._semantic_store.confirm(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            table_name=table_name,
            column_name=column_name,
            semantic_field=semantic_field,
        )

    def resume_mapping(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        confirmations: tuple[tuple[str, str, SemanticField], ...],
        actor_id: str,
        idempotency_key: str,
    ) -> MappingResumeResult:
        actor_id = actor_id.strip()
        if not actor_id:
            raise MappingResumeConflictError("Mapping resume requires a human actor")
        ordered = tuple(sorted(confirmations, key=lambda item: (item[0], item[1])))
        keys = tuple((table_name, column_name) for table_name, column_name, _ in ordered)
        if not ordered:
            raise DataIntakeError("At least one semantic confirmation is required")
        if len(keys) != len(set(keys)):
            raise DataIntakeError("Semantic confirmation columns must be unique")
        request_sha256 = self._mapping_resume_request_sha256(
            dataset_id=dataset_id,
            actor_id=actor_id,
            confirmations=ordered,
        )
        command_sha256 = hashlib.sha256(f"{actor_id}\0{idempotency_key}".encode()).hexdigest()
        receipt_path = self._storage_root / str(workspace_id) / str(dataset_id) / "commands" / f"mapping-resume-{command_sha256}.json"
        replay = self._load_mapping_resume_receipt(
            receipt_path,
            request_sha256=request_sha256,
        )
        if replay is not None:
            return replay
        view = self.get_view(workspace_id, dataset_id)
        for table_name, column_name, _ in ordered:
            try:
                view.profile.table(table_name).column(column_name)
            except KeyError as exc:
                raise DataIntakeError(f"Unknown Dataset column: {table_name}.{column_name}") from exc
        persisted = self._semantic_store.confirm_many(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            confirmations=ordered,
            confirmed_by=actor_id,
        )
        refreshed = self.get_view(workspace_id, dataset_id)
        receipt = MappingResumeReceipt(
            request_sha256=request_sha256,
            actor_id=actor_id,
            confirmations=persisted,
            mappings=refreshed.mappings,
            capabilities=refreshed.capabilities,
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with receipt_path.open("x", encoding="utf-8") as handle:
                json.dump(
                    receipt.model_dump(mode="json"),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
        except FileExistsError:
            concurrent = self._load_mapping_resume_receipt(
                receipt_path,
                request_sha256=request_sha256,
            )
            if concurrent is None:
                raise MappingResumeConflictError("Mapping resume receipt was not persisted")
            return concurrent
        persisted_result = self._load_mapping_resume_receipt(
            receipt_path,
            request_sha256=request_sha256,
        )
        if persisted_result is None:
            raise MappingResumeConflictError("Mapping resume receipt was not persisted")
        return MappingResumeResult(
            confirmations=persisted_result.confirmations,
            mappings=persisted_result.mappings,
            capabilities=persisted_result.capabilities,
            created=True,
            replayed=False,
        )

    def _build_view(self, manifest: DataBundleManifest) -> DatasetView:
        profile = self._profiler.profile(manifest)
        mappings = self._mapper.map(profile)
        capabilities = self._capabilities.assess(profile, mappings)
        return DatasetView(
            manifest=manifest,
            profile=profile,
            mappings=mappings,
            capabilities=capabilities,
        )

    @staticmethod
    def _sort_timestamp(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _mapping_resume_request_sha256(
        *,
        dataset_id: DatasetId,
        actor_id: str,
        confirmations: tuple[tuple[str, str, SemanticField], ...],
    ) -> str:
        payload = {
            "actor_id": actor_id,
            "confirmations": [
                {
                    "column_name": column_name,
                    "semantic_field": semantic_field.value,
                    "table_name": table_name,
                }
                for table_name, column_name, semantic_field in confirmations
            ],
            "dataset_id": str(dataset_id),
        }
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _load_mapping_resume_receipt(
        path: Path,
        *,
        request_sha256: str,
    ) -> MappingResumeResult | None:
        if not path.is_file():
            return None
        try:
            receipt = MappingResumeReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MappingResumeConflictError("Mapping resume receipt is invalid") from exc
        if receipt.request_sha256 != request_sha256:
            raise MappingResumeConflictError("Mapping resume idempotency key conflicts with a prior request")
        return MappingResumeResult(
            confirmations=receipt.confirmations,
            mappings=receipt.mappings,
            capabilities=receipt.capabilities,
            created=False,
            replayed=True,
        )

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if not filename or filename in {".", ".."} or Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise DataIntakeError("Uploaded filename must be a plain file name")
