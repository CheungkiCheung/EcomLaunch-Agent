"""Middleware for automatic thread title generation."""

import logging
import re
from typing import TYPE_CHECKING, Any, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.config import get_config
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.dynamic_context_middleware import is_dynamic_context_reminder
from deerflow.config.title_config import get_title_config
from deerflow.models import create_chat_model

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig
    from deerflow.config.title_config import TitleConfig

logger = logging.getLogger(__name__)

_UPLOADED_FILES_RE = re.compile(
    r"<uploaded_files>[\s\S]*?</uploaded_files>",
    flags=re.IGNORECASE,
)


class TitleMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    title: NotRequired[str | None]


class TitleMiddleware(AgentMiddleware[TitleMiddlewareState]):
    """Automatically generate a title for the thread after the first user message."""

    state_schema = TitleMiddlewareState

    def __init__(
        self,
        *,
        app_config: "AppConfig | None" = None,
        title_config: "TitleConfig | None" = None,
        use_model: bool = True,
        local_title_rules: list[dict[str, Any]] | None = None,
        local_title_fallback: str | None = None,
    ):
        super().__init__()
        self._app_config = app_config
        self._title_config = title_config
        self._use_model = use_model
        self._local_title_rules = tuple(local_title_rules or ())
        self._local_title_fallback = local_title_fallback

    def _get_title_config(self):
        if self._title_config is not None:
            return self._title_config
        if self._app_config is not None:
            return self._app_config.title
        return get_title_config()

    def _normalize_content(self, content: object) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = [self._normalize_content(item) for item in content]
            return "\n".join(part for part in parts if part)

        if isinstance(content, dict):
            text_value = content.get("text")
            if isinstance(text_value, str):
                return text_value

            nested_content = content.get("content")
            if nested_content is not None:
                return self._normalize_content(nested_content)

        return ""

    @staticmethod
    def _is_user_message_for_title(message: object) -> bool:
        return getattr(message, "type", None) == "human" and not is_dynamic_context_reminder(message)

    def _should_generate_title(self, state: TitleMiddlewareState) -> bool:
        """Check if we should generate a title for this thread."""
        config = self._get_title_config()
        if not config.enabled:
            return False

        # Check if thread already has a title in state
        if state.get("title"):
            return False

        # Check if this is the first turn (has at least one user message and one assistant response)
        messages = state.get("messages", [])
        if len(messages) < 2:
            return False

        # Count user and assistant messages
        user_messages = [m for m in messages if self._is_user_message_for_title(m)]
        assistant_messages = [m for m in messages if m.type == "ai"]

        # Generate title after first complete exchange
        return len(user_messages) == 1 and len(assistant_messages) >= 1

    def _build_title_prompt(self, state: TitleMiddlewareState) -> tuple[str, str]:
        """Extract user/assistant messages and build the title prompt.

        Returns (prompt_string, user_msg) so callers can use user_msg as fallback.
        """
        config = self._get_title_config()
        messages = state.get("messages", [])

        user_msg_content = next((m.content for m in messages if self._is_user_message_for_title(m)), "")
        assistant_msg_content = next((m.content for m in messages if m.type == "ai"), "")

        user_msg = self._normalize_content(user_msg_content)
        assistant_msg = self._strip_think_tags(self._normalize_content(assistant_msg_content))

        prompt = config.prompt_template.format(
            max_words=config.max_words,
            user_msg=user_msg[:500],
            assistant_msg=assistant_msg[:500],
        )
        return prompt, user_msg

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> blocks emitted by reasoning models (e.g. minimax, DeepSeek-R1)."""
        return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    def _parse_title(self, content: object) -> str:
        """Normalize model output into a clean title string."""
        config = self._get_title_config()
        title_content = self._normalize_content(content)
        title_content = self._strip_think_tags(title_content)
        title = title_content.strip().strip('"').strip("'")
        return title[: config.max_chars] if len(title) > config.max_chars else title

    def _fallback_title(self, user_msg: str) -> str:
        config = self._get_title_config()
        cleaned_user_msg = self._clean_local_title_input(user_msg)
        for rule in self._local_title_rules:
            keywords = rule.get("keywords")
            title = rule.get("title")
            if not isinstance(keywords, list) or not isinstance(title, str):
                continue
            if any(
                isinstance(keyword, str)
                and keyword.strip()
                and keyword.strip() in cleaned_user_msg
                for keyword in keywords
            ):
                return title[: config.max_chars]

        if self._local_title_fallback:
            return self._local_title_fallback[: config.max_chars]

        fallback_chars = min(config.max_chars, 50)
        if len(cleaned_user_msg) > fallback_chars:
            return cleaned_user_msg[:fallback_chars].rstrip() + "..."
        return cleaned_user_msg if cleaned_user_msg else "New Conversation"

    @staticmethod
    def _clean_local_title_input(user_msg: str) -> str:
        without_uploaded_files = _UPLOADED_FILES_RE.sub(" ", user_msg)
        return re.sub(r"\s+", " ", without_uploaded_files).strip()

    def _get_runnable_config(self) -> dict[str, Any]:
        """Inherit the parent RunnableConfig and add middleware tag.

        This ensures RunJournal identifies LLM calls from this middleware
        as ``middleware:title`` instead of ``lead_agent``.
        """
        try:
            parent = get_config()
        except Exception:
            parent = {}
        config = {**parent}
        config["run_name"] = "title_agent"
        config["tags"] = [*(config.get("tags") or []), "middleware:title"]
        return config

    def _generate_title_result(self, state: TitleMiddlewareState) -> dict | None:
        """Generate a local fallback title without blocking on an LLM call."""
        if not self._should_generate_title(state):
            return None

        _, user_msg = self._build_title_prompt(state)
        return {"title": self._fallback_title(user_msg)}

    async def _agenerate_title_result(self, state: TitleMiddlewareState) -> dict | None:
        """Generate a title asynchronously and fall back locally on failure."""
        if not self._should_generate_title(state):
            return None

        config = self._get_title_config()
        prompt, user_msg = self._build_title_prompt(state)

        if not self._use_model:
            return {"title": self._fallback_title(user_msg)}

        try:
            # attach_tracing=False because ``_get_runnable_config()`` inherits
            # the graph-level RunnableConfig (set in ``_make_lead_agent``) whose
            # callbacks already carry tracing handlers; binding them again at
            # the model level would emit duplicate spans.
            model_kwargs = {"thinking_enabled": False, "attach_tracing": False}
            if self._app_config is not None:
                model_kwargs["app_config"] = self._app_config
            if config.model_name:
                model = create_chat_model(name=config.model_name, **model_kwargs)
            else:
                model = create_chat_model(**model_kwargs)
            response = await model.ainvoke(prompt, config=self._get_runnable_config())
            title = self._parse_title(response.content)
            if title:
                return {"title": title}
        except Exception:
            logger.debug("Failed to generate async title; falling back to local title", exc_info=True)
        return {"title": self._fallback_title(user_msg)}

    @override
    def after_model(self, state: TitleMiddlewareState, runtime: Runtime) -> dict | None:
        return self._generate_title_result(state)

    @override
    async def aafter_model(self, state: TitleMiddlewareState, runtime: Runtime) -> dict | None:
        return await self._agenerate_title_result(state)
