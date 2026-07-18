from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.validators.core import (  # noqa: E402
    validate_artifact_bundle,
    validate_fixture_collection,
)


def test_golden_artifact_fixture_passes():
    result = validate_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/golden/golden-001")

    assert result.ok, result.errors
    assert result.artifact_count >= 10


def test_broken_private_metric_fixture_fails():
    result = validate_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/broken/broken-003")

    assert not result.ok
    assert any("private metric" in error for error in result.errors)


def test_fixture_collections_have_required_pass_fail_counts():
    golden = validate_fixture_collection(REPO_ROOT / "evals/opensku/fixtures/golden")
    broken = validate_fixture_collection(REPO_ROOT / "evals/opensku/fixtures/broken")

    assert golden.bundle_count == 10
    assert golden.passed_count == 10
    assert golden.failed_count == 0
    assert broken.bundle_count == 10
    assert broken.failed_count == 10

