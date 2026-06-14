from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ARTIFACTS = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}


def test_ecom_launch_skill_defaults_to_full_validation_pack():
    skill = (REPO_ROOT / "skills" / "custom" / "ecom-launch" / "SKILL.md").read_text(
        encoding="utf-8",
    )

    assert "validate-launch -> Launch Validation Pack" in skill
    assert "`validate-launch` means a full Launch Validation Pack by default" in skill
    assert "Only reduce scope when the user explicitly asks" in skill
    assert "three-file smoke test" in skill
    assert REQUIRED_ARTIFACTS.issubset(set(_artifact_mentions(skill)))


def test_ecom_launch_soul_defaults_to_full_validation_pack():
    soul = (REPO_ROOT / "agents" / "ecom-launch" / "SOUL.md").read_text(
        encoding="utf-8",
    )

    assert "validate-launch -> Launch Validation Pack" in soul
    assert "By default, `validate-launch` means a complete Launch Validation Pack" in soul
    assert "Only run a smoke test" in soul
    assert "use all five ecommerce roles" in soul
    assert REQUIRED_ARTIFACTS.issubset(set(_artifact_mentions(soul)))


def _artifact_mentions(text: str) -> list[str]:
    return [artifact for artifact in REQUIRED_ARTIFACTS if artifact in text]
