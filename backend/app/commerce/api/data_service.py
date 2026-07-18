"""File-backed deterministic dataset application service."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.commerce.data.capabilities import CapabilityProfile, CapabilityRegistry
from app.commerce.data.intake import DataBundleManifest, DataIntakeError, DataIntakeService
from app.commerce.data.profiler import DataProfiler, DatasetProfile
from app.commerce.data.semantic_mapper import (
    SemanticMapper,
    SemanticMappingProfile,
    WorkspaceSemanticStore,
)
from app.commerce.domain.ids import DatasetId, WorkspaceId


class DatasetNotFoundError(LookupError):
    """The requested Dataset does not exist in the requested Workspace."""


@dataclass(frozen=True)
class DatasetView:
    manifest: DataBundleManifest
    profile: DatasetProfile
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile


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

    def get_view(self, workspace_id: WorkspaceId, dataset_id: DatasetId) -> DatasetView:
        manifest_path = (
            self._storage_root
            / str(workspace_id)
            / str(dataset_id)
            / "manifest.json"
        )
        if not manifest_path.is_file():
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
        try:
            manifest = DataBundleManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise DataIntakeError(f"Stored Dataset manifest is invalid: {dataset_id}") from exc
        return self._build_view(manifest)

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
    def _validate_filename(filename: str) -> None:
        if (
            not filename
            or filename in {".", ".."}
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
        ):
            raise DataIntakeError("Uploaded filename must be a plain file name")
