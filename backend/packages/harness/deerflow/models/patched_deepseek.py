"""Patched ChatDeepSeek that preserves reasoning_content in multi-turn conversations.

This module provides a patched version of ChatDeepSeek that properly handles
reasoning_content when sending messages back to the API. The original implementation
stores reasoning_content in additional_kwargs but doesn't include it when making
subsequent API calls, which causes errors with APIs that require reasoning_content
on all assistant messages when thinking mode is enabled.
"""

from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_deepseek import ChatDeepSeek

from deerflow.models.assistant_payload_replay import restore_assistant_payloads, restore_reasoning_content


class PatchedChatDeepSeek(ChatDeepSeek):
    """ChatDeepSeek with proper reasoning_content preservation.

    When using thinking/reasoning enabled models, the API expects reasoning_content
    to be present on ALL assistant messages in multi-turn conversations. This patched
    version ensures reasoning_content from additional_kwargs is included in the
    request payload.
    """

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"api_key": "DEEPSEEK_API_KEY", "openai_api_key": "DEEPSEEK_API_KEY"}

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Get request payload with reasoning_content preserved.

        Overrides the parent method to inject reasoning_content from
        additional_kwargs into assistant messages in the payload.
        """
        # Get the original messages before conversion
        original_messages = self._convert_input(input_).to_messages()

        # Call parent to get the base payload
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        configured_extra_body = getattr(self, "extra_body", None)
        invocation_extra_body = kwargs.get("extra_body")
        configured_thinking = (
            configured_extra_body.get("thinking")
            if isinstance(configured_extra_body, dict)
            else None
        )
        invocation_thinking = (
            invocation_extra_body.get("thinking")
            if isinstance(invocation_extra_body, dict)
            else None
        )
        effective_thinking = (
            invocation_thinking
            if isinstance(invocation_thinking, dict)
            else configured_thinking
        )
        thinking_disabled = (
            isinstance(effective_thinking, dict)
            and effective_thinking.get("type") == "disabled"
        )
        if not thinking_disabled:
            restore_assistant_payloads(
                payload.get("messages", []),
                original_messages,
                restore_reasoning_content,
            )

        return payload

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        """Preserve DeepSeek's streamed response ID for request telemetry.

        ``langchain-openai`` currently keeps model/fingerprint/finish metadata
        but drops the top-level Chat Completions ``id`` while converting stream
        chunks. DeepSeek returns one stable UUID on every raw chunk, so attach it
        to each message chunk before LangChain aggregates the final AIMessage.
        """

        generation = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        response_id = chunk.get("id")
        actual_model_identity = chunk.get("model")
        choices = chunk.get("choices")
        terminal_chunk = bool(
            isinstance(choices, list)
            and any(
                isinstance(choice, dict)
                and choice.get("finish_reason") is not None
                for choice in choices
            )
        )
        if generation is not None and terminal_chunk:
            metadata = generation.message.response_metadata
            if actual_model_identity:
                metadata["actual_model_identity"] = str(actual_model_identity)
            if response_id:
                normalized_response_id = str(response_id)
                metadata["id"] = normalized_response_id
                metadata["provider_request_id"] = normalized_response_id
                metadata["provider_request_id_source"] = "response.id"
            if getattr(self, "max_retries", None) == 0:
                metadata["retry_count"] = 0
        return generation
