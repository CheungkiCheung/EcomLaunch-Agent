from types import SimpleNamespace

from deerflow.tools.tools import _tool_group_requested


def test_web_fast_group_excludes_last30days_but_keeps_normal_web_tools() -> None:
    assert _tool_group_requested(SimpleNamespace(name="web_search", group="web"), ["web_fast"])
    assert _tool_group_requested(SimpleNamespace(name="web_fetch", group="web"), ["web_fast"])
    assert not _tool_group_requested(SimpleNamespace(name="last30days", group="web"), ["web_fast"])
    assert _tool_group_requested(SimpleNamespace(name="last30days", group="web"), ["web"])
