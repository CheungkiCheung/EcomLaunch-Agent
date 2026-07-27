"""Callback handler that collects LLM token usage within a subagent.

Each subagent execution creates its own collector. After the subagent
finishes, the collected records are transferred to the parent RunJournal
via :meth:`RunJournal.record_external_llm_usage_records`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class SubagentTokenCollector(BaseCallbackHandler):
    """Lightweight callback handler that collects LLM token usage within a subagent."""

    def __init__(self, caller: str):
        super().__init__()
        self.caller = caller
        self._records: list[dict[str, int | str]] = []
        self._counted_run_ids: set[str] = set()

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        if rid in self._counted_run_ids:
            return

        for generation in response.generations:
            for gen in generation:
                if not hasattr(gen, "message"):
                    continue
                usage = getattr(gen.message, "usage_metadata", None)
                usage_dict = dict(usage) if usage else {}
                input_tk = usage_dict.get("input_tokens", 0) or 0
                output_tk = usage_dict.get("output_tokens", 0) or 0
                total_tk = usage_dict.get("total_tokens", 0) or 0
                if total_tk <= 0:
                    total_tk = input_tk + output_tk
                if total_tk <= 0:
                    continue
                metadata: dict[str, Any] = {}
                response_metadata = getattr(gen.message, "response_metadata", None)
                if isinstance(response_metadata, Mapping):
                    metadata.update(response_metadata)
                generation_info = getattr(gen, "generation_info", None)
                if isinstance(generation_info, Mapping):
                    metadata.update(generation_info)

                headers_raw = metadata.get("headers")
                headers = (
                    {
                        str(key).casefold(): str(value)
                        for key, value in headers_raw.items()
                    }
                    if isinstance(headers_raw, Mapping)
                    else {}
                )
                actual_model_identity = next(
                    (
                        value.strip()
                        for key in ("model_name", "model")
                        if isinstance((value := metadata.get(key)), str)
                        and value.strip()
                    ),
                    None,
                )
                if actual_model_identity is None:
                    actual_model_identity = next(
                        (
                            headers[key]
                            for key in (
                                "x-deepseek-model",
                                "x-model-name",
                                "x-model",
                            )
                            if headers.get(key)
                        ),
                        None,
                    )
                provider_request_id = next(
                    (
                        headers[key]
                        for key in (
                            "x-request-id",
                            "x-deepseek-request-id",
                            "request-id",
                        )
                        if headers.get(key)
                    ),
                    None,
                )
                response_id = metadata.get("id")
                provider_response_id = (
                    str(response_id) if response_id is not None else None
                )
                provider_request_id = provider_request_id or provider_response_id
                stop_reason_value = metadata.get("finish_reason")
                fingerprint_value = metadata.get("system_fingerprint")

                self._counted_run_ids.add(rid)
                record: dict[str, int | str] = {
                    "source_run_id": rid,
                    "caller": self.caller,
                    "input_tokens": input_tk,
                    "output_tokens": output_tk,
                    "total_tokens": total_tk,
                }
                optional_evidence = {
                    "actual_model_identity": actual_model_identity,
                    "provider_request_id": provider_request_id,
                    "provider_response_id": provider_response_id,
                    "stop_reason": (
                        str(stop_reason_value)
                        if stop_reason_value is not None
                        else None
                    ),
                    "system_fingerprint": (
                        str(fingerprint_value)
                        if fingerprint_value is not None
                        else None
                    ),
                }
                record.update(
                    {
                        key: value
                        for key, value in optional_evidence.items()
                        if value is not None
                    }
                )
                self._records.append(record)
                return

    def snapshot_records(self) -> list[dict[str, int | str]]:
        """Return a copy of the accumulated usage records."""
        return list(self._records)
