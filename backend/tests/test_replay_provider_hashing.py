from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from replay_provider import hash_messages


def _parallel_write_history(*, reverse_results: bool) -> list:
    messages = [
        HumanMessage(content="build pack"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "write_file", "args": {"path": "/mnt/user-data/outputs/a.md"}, "id": "write-a"},
                {"name": "write_file", "args": {"path": "/mnt/user-data/outputs/b.md"}, "id": "write-b"},
            ],
        ),
    ]
    if reverse_results:
        messages.extend(
            [
                ToolMessage(
                    content="OK: wrote 20 bytes to /mnt/user-data/outputs/b.md.\nConfigured Pack status: 1/2 required files written in this request. Missing required files: a.md.",
                    tool_call_id="write-b",
                    name="write_file",
                ),
                ToolMessage(
                    content="OK: wrote 10 bytes to /mnt/user-data/outputs/a.md.\nConfigured Pack status: complete (2/2). All required files were written in this request.",
                    tool_call_id="write-a",
                    name="write_file",
                ),
            ]
        )
    else:
        messages.extend(
            [
                ToolMessage(
                    content="OK: wrote 10 bytes to /mnt/user-data/outputs/a.md.\nConfigured Pack status: 1/2 required files written in this request. Missing required files: b.md.",
                    tool_call_id="write-a",
                    name="write_file",
                ),
                ToolMessage(
                    content="OK: wrote 20 bytes to /mnt/user-data/outputs/b.md.\nConfigured Pack status: complete (2/2). All required files were written in this request.",
                    tool_call_id="write-b",
                    name="write_file",
                ),
            ]
        )
    return messages


def test_parallel_write_result_order_and_pack_counter_do_not_change_hash() -> None:
    assert hash_messages(_parallel_write_history(reverse_results=False)) == hash_messages(_parallel_write_history(reverse_results=True))


def test_stable_tool_result_content_still_changes_hash() -> None:
    original = _parallel_write_history(reverse_results=False)
    changed = _parallel_write_history(reverse_results=False)
    changed[-1] = ToolMessage(
        content="Error: b.md could not be written",
        tool_call_id="write-b",
        name="write_file",
    )

    assert hash_messages(original) != hash_messages(changed)
