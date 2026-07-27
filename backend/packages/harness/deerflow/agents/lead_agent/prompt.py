from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Collection
from functools import lru_cache
from typing import TYPE_CHECKING

from deerflow.config.agents_config import load_agent_soul
from deerflow.skills.storage import get_or_new_skill_storage
from deerflow.skills.types import Skill, SkillCategory
from deerflow.subagents import get_available_subagent_names
from deerflow.tools.builtins.tool_search import get_deferred_tools_prompt_section

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig

logger = logging.getLogger(__name__)

_ENABLED_SKILLS_REFRESH_WAIT_TIMEOUT_SECONDS = 5.0
_enabled_skills_lock = threading.Lock()
_enabled_skills_cache: list[Skill] | None = None
_enabled_skills_by_config_cache: dict[int, tuple[object, list[Skill]]] = {}
_enabled_skills_refresh_active = False
_enabled_skills_refresh_version = 0
_enabled_skills_refresh_event = threading.Event()


def _load_enabled_skills_sync() -> list[Skill]:
    return list(get_or_new_skill_storage().load_skills(enabled_only=True))


def _start_enabled_skills_refresh_thread() -> None:
    threading.Thread(
        target=_refresh_enabled_skills_cache_worker,
        name="deerflow-enabled-skills-loader",
        daemon=True,
    ).start()


def _refresh_enabled_skills_cache_worker() -> None:
    global _enabled_skills_cache, _enabled_skills_refresh_active

    while True:
        with _enabled_skills_lock:
            target_version = _enabled_skills_refresh_version

        try:
            skills = _load_enabled_skills_sync()
        except Exception:
            logger.exception("Failed to load enabled skills for prompt injection")
            skills = []

        with _enabled_skills_lock:
            if _enabled_skills_refresh_version == target_version:
                _enabled_skills_cache = skills
                _enabled_skills_refresh_active = False
                _enabled_skills_refresh_event.set()
                return

            # A newer invalidation happened while loading. Keep the worker alive
            # and loop again so the cache always converges on the latest version.
            _enabled_skills_cache = None


def _ensure_enabled_skills_cache() -> threading.Event:
    global _enabled_skills_refresh_active

    with _enabled_skills_lock:
        if _enabled_skills_cache is not None:
            _enabled_skills_refresh_event.set()
            return _enabled_skills_refresh_event
        if _enabled_skills_refresh_active:
            return _enabled_skills_refresh_event
        _enabled_skills_refresh_active = True
        _enabled_skills_refresh_event.clear()

    _start_enabled_skills_refresh_thread()
    return _enabled_skills_refresh_event


def _invalidate_enabled_skills_cache() -> threading.Event:
    global _enabled_skills_cache, _enabled_skills_refresh_active, _enabled_skills_refresh_version

    _get_cached_skills_prompt_section.cache_clear()
    with _enabled_skills_lock:
        _enabled_skills_cache = None
        _enabled_skills_by_config_cache.clear()
        _enabled_skills_refresh_version += 1
        _enabled_skills_refresh_event.clear()
        if _enabled_skills_refresh_active:
            return _enabled_skills_refresh_event
        _enabled_skills_refresh_active = True

    _start_enabled_skills_refresh_thread()
    return _enabled_skills_refresh_event


def prime_enabled_skills_cache() -> None:
    _ensure_enabled_skills_cache()


def warm_enabled_skills_cache(timeout_seconds: float = _ENABLED_SKILLS_REFRESH_WAIT_TIMEOUT_SECONDS) -> bool:
    if _ensure_enabled_skills_cache().wait(timeout=timeout_seconds):
        return True

    logger.warning("Timed out waiting %.1fs for enabled skills cache warm-up", timeout_seconds)
    return False


def _get_enabled_skills():
    return get_cached_enabled_skills()


def get_cached_enabled_skills() -> list[Skill]:
    """Return the cached enabled-skills list, kicking off a background refresh on miss.

    Safe to call from request paths: never blocks on disk I/O. Returns an empty
    list on cache miss; the next call will see the warmed result.
    """
    with _enabled_skills_lock:
        cached = _enabled_skills_cache

    if cached is not None:
        return list(cached)

    _ensure_enabled_skills_cache()
    return []


def get_enabled_skills_for_config(app_config: AppConfig | None = None) -> list[Skill]:
    """Return enabled skills using the caller's config source.

    When a concrete ``app_config`` is supplied, cache the loaded skills by that
    config object's identity so request-scoped config injection still resolves
    skill paths from the matching config without rescanning storage on every
    agent factory call.
    """
    if app_config is None:
        return _get_enabled_skills()

    cache_key = id(app_config)
    with _enabled_skills_lock:
        cached = _enabled_skills_by_config_cache.get(cache_key)
        if cached is not None:
            cached_config, cached_skills = cached
            if cached_config is app_config:
                return list(cached_skills)

    skills = list(get_or_new_skill_storage(app_config=app_config).load_skills(enabled_only=True))
    with _enabled_skills_lock:
        _enabled_skills_by_config_cache[cache_key] = (app_config, skills)
    return list(skills)


def _skill_mutability_label(category: SkillCategory | str) -> str:
    return "[custom, editable]" if category == SkillCategory.CUSTOM else "[built-in]"


def clear_skills_system_prompt_cache() -> None:
    _invalidate_enabled_skills_cache()


async def refresh_skills_system_prompt_cache_async() -> None:
    await asyncio.to_thread(_invalidate_enabled_skills_cache().wait)


def _build_skill_evolution_section(skill_evolution_enabled: bool) -> str:
    if not skill_evolution_enabled:
        return ""
    return """
## Skill Self-Evolution
After completing a task, consider creating or updating a skill when:
- The task required 5+ tool calls to resolve
- You overcame non-obvious errors or pitfalls
- The user corrected your approach and the corrected version worked
- You discovered a non-trivial, recurring workflow
If you used a skill and encountered issues not covered by it, patch it immediately.
Prefer patch over edit. Before creating a new skill, confirm with the user first.
Skip simple one-off tasks.
"""


def _build_available_subagents_description(
    available_names: list[str],
    bash_available: bool,
    *,
    app_config: AppConfig | None = None,
    require_explicit_subagent_scope: bool = False,
) -> str:
    """Dynamically build subagent type descriptions from registry.

    Mirrors Codex's pattern where agent_type_description is dynamically generated
    from all registered roles, so the LLM knows about every available type.
    """
    # Built-in descriptions (kept for backward compatibility with existing prompt quality)
    builtin_descriptions = {
        "general-purpose": "Fallback for non-trivial tasks that do not match a more specialized subagent.",
        "bash": (
            "For command execution (git, build, test, deploy operations)" if bash_available else "Not available in the current sandbox configuration. Use direct file/web tools or switch to AioSandboxProvider for isolated shell access."
        ),
    }

    # Lazy import moved outside loop to avoid repeated import overhead
    from deerflow.subagents.registry import get_subagent_config

    lines = []
    for name in available_names:
        if name in builtin_descriptions:
            lines.append(f"- **{name}**: {builtin_descriptions[name]}")
        else:
            config = get_subagent_config(name, app_config=app_config)
            if config is not None:
                desc = config.description.split("\n")[0].strip()  # First line only for brevity
                budget_parts = []
                if config.max_tool_rounds is not None:
                    budget_parts.append(f"max_tool_rounds={config.max_tool_rounds}")
                if config.max_tool_calls is not None:
                    budget_parts.append(f"max_tool_calls={config.max_tool_calls}")
                budget = ""
                if budget_parts:
                    policy = (
                        "Parent 必须显式传入不超过此上限的预算"
                        if require_explicit_subagent_scope
                        else "Parent 通常省略预算参数；显式传入只能收窄"
                    )
                    budget = f"；预算上限：{', '.join(budget_parts)}（{policy}）"
                lines.append(f"- **{name}**: {desc}{budget}")

    return "\n".join(lines)


def _build_specialized_subagent_guidance(available_names: list[str]) -> str:
    """Build role-selection guidance when custom subagents are configured."""
    custom_names = [name for name in available_names if name not in {"general-purpose", "bash"}]
    if not custom_names:
        return ""

    names = ", ".join(f"`{name}`" for name in custom_names)
    return f"""
**Specialized Subagent Selection:**
- Specialized subagents are available: {names}.
- When a sub-task matches one of these roles, use that exact role name as `subagent_type`.
- Do NOT use `general-purpose` for work covered by a specialized subagent.
- Reserve `general-purpose` only for meaningful sub-tasks with no matching specialist.
- The `description` field is only the short UI label; the actual routing key is `subagent_type`.
"""


def _build_subagent_usage_examples(
    available_names: list[str],
    n: int,
    *,
    require_explicit_subagent_scope: bool = False,
) -> str:
    """Build durable lifecycle examples with exact custom role routing."""
    if require_explicit_subagent_scope:
        return f"""**显式最小派工模板（同轮最多 {n} 个）**

```python
spawn_task(
    description="简短中文任务名",
    prompt="完整、独立、可执行的目标与停止条件...",
    subagent_type="<匹配当前目标的 Profile>",
    skills=["<已启用 Skill 名称>"],
    tools=["<完成目标所需的最小 Tool>"],
    max_tool_rounds=1,
    max_tool_calls=1,
)
```

需要并行时，在同一个模型响应中重复完整的 `spawn_task` 参数模板；不要省略
`skills`、`tools`、`max_tool_rounds` 或 `max_tool_calls`。任务启动后再统一等待：

```python
wait_task(task_ids=["id-a", "id-b"], mode="all", timeout_seconds=60)
```
"""

    custom_names = [name for name in available_names if name not in {"general-purpose", "bash"}]
    if len(custom_names) >= 3:
        a, b, c = custom_names[:3]
        return f"""**示例：同一轮并行启动三个独立任务（上限 {n}）**

```python
# 三个调用必须放在同一个模型响应中，ToolNode 才能并行分发。
spawn_task(description="{a} 工作流", prompt="独立目标与输入...", subagent_type="{a}")
spawn_task(description="{b} 工作流", prompt="独立目标与输入...", subagent_type="{b}")
spawn_task(description="{c} 工作流", prompt="独立目标与输入...", subagent_type="{c}")
```

任务启动后，Parent 可以先执行其他确定性工具，再一次等待：

```python
wait_task(task_ids=["id-a", "id-b", "id-c"], mode="all", timeout_seconds=60)
```
"""

    return f"""**示例：经营诊断的动态并行委派（上限 {n}）**

```python
# 用户问复杂、可拆分的经营问题时，在同一响应并行启动任务。
spawn_task(description="检查数据能力", prompt="检查字段、口径和数据限制...", subagent_type="general-purpose")
spawn_task(description="分析异常贡献", prompt="计算分段贡献并寻找反证...", subagent_type="general-purpose")
spawn_task(description="独立验证结论", prompt="使用 fresh context 验证关键结论...", subagent_type="general-purpose")
```

```python
# 等任意一个结果以便先推进，或等全部结果后综合。
wait_task(task_ids=["id-1", "id-2", "id-3"], mode="any", timeout_seconds=30)
wait_task(task_ids=["id-1", "id-2", "id-3"], mode="all", timeout_seconds=60)
```
"""


def _build_subagent_section(
    max_concurrent: int,
    *,
    app_config: AppConfig | None = None,
    subagent_required: bool = False,
    complexity_tool_call_threshold: int = 2,
    required_subagent_types: Collection[str] = (),
    require_explicit_subagent_scope: bool = False,
) -> str:
    """Build the subagent system prompt section with dynamic concurrency limit.

    Args:
        max_concurrent: Maximum number of concurrent subagent calls allowed per response.

    Returns:
        Formatted subagent section string.
    """
    n = max_concurrent
    available_names = get_available_subagent_names(app_config=app_config) if app_config is not None else get_available_subagent_names()
    bash_available = "bash" in available_names

    # Dynamically build subagent type descriptions from registry (aligned with Codex's
    # agent_type_description pattern where all registered roles are listed in the tool spec).
    available_subagents = _build_available_subagents_description(
        available_names,
        bash_available,
        app_config=app_config,
        require_explicit_subagent_scope=require_explicit_subagent_scope,
    )
    specialized_subagent_guidance = _build_specialized_subagent_guidance(available_names)
    usage_examples = _build_subagent_usage_examples(
        available_names,
        n,
        require_explicit_subagent_scope=require_explicit_subagent_scope,
    )
    direct_tools = "bash、ls、read_file、web_search" if bash_available else "ls、read_file、web_search"
    direct_tools_security_hint = "available tools (bash, ls, read_file, web_search, etc.)" if bash_available else "available tools (ls, read_file, web_search, etc.)"
    direct_execution_example = 'bash("npm test")' if bash_available else 'read_file("/mnt/user-data/workspace/README.md")'
    required_profiles = tuple(dict.fromkeys(profile.strip() for profile in required_subagent_types if isinstance(profile, str) and profile.strip()))
    required_profile_text = "、".join(f"`{profile}`" for profile in required_profiles)
    if not required_profile_text:
        required_profile_text = "至少一个由当前任务动态选择的 Profile"
    verifier_requirement = "\n- `verifier` 必须使用 fresh ContextPacket，并通过 `source_refs` 中的 `task:<task_id>` 引用当前 Run 中已完成的前置任务；不能让同一上下文自我背书。" if "verifier" in required_profiles else ""
    required_delivery_contract = (
        f"""
### 强制交付策略

- 当当前 Run 累计达到 {complexity_tool_call_threshold} 个直接工作 Tool 调用时，必须在最终回答前完成必需的 Durable Subagent Profile：{required_profile_text}。
- 应尽早拆分可隔离的分析或探索任务，调用 `spawn_task` 后用 `wait_task` 获取终态；不要等 Parent 完成全部工具链后才补形式化派工。{verifier_requirement}
- 最终综合只能使用当前 Run 已完成任务的可追溯结果。不允许 Parent 完成全部分析后跳过 Durable Task。
- 若必需 Profile 或可追溯任务结果缺失，Harness 将 fail-closed 并阻止交付；不要把未经独立核验的结论包装成最终答案。
"""
        if subagent_required
        else ""
    )
    explicit_scope_contract = (
        """
### 显式派工范围

- 每次 spawn_task 都必须显式传入：非空 skills、非空 tools、max_tool_rounds 和 max_tool_calls。
- 四项都必须是完成当前目标所需的最小范围；省略或传空列表会被 Harness 拒绝。
- verifier 的 tools 必须包含独立重算核心结论所需的确定性 Tool，不能只读取前置任务文本。
- verifier 不能作为没有前置 Task 的首个任务；source_refs 只能复制 wait_task 返回的精确 task_id，写成 task:<task_id>，不得使用任务描述、自造别名或示例占位符。
"""
        if require_explicit_subagent_scope
        else ""
    )
    dispatch_scope_rule = (
        "派工时必须显式传入非空 `skills`、非空 `tools`、`max_tool_rounds` 和 "
        "`max_tool_calls`，并使用完成目标所需的最小能力与预算；任何一项都不能省略。"
        if require_explicit_subagent_scope
        else "派工时用 `skills`、`tools`、`max_tool_rounds` 和 `max_tool_calls` "
        "给出完成目标所需的最小能力与预算；通常省略预算参数并采用 Profile 默认上限，"
        "显式传入只能收窄，不能扩权。"
    )
    return f"""<subagent_system>
## Durable Parent–Subagent Harness

你是用户唯一持续交互的 Parent Agent。Subagent 是按需创建的隔离工作上下文，不是每次固定运行的 Crew。

### 可用 Subagent

{available_subagents}
{specialized_subagent_guidance}

### 决策规则

1. 简单问答、单步读取或确定性计算：直接回答或直接调用 {direct_tools} 等工具，不派 Subagent。
2. 任务复杂、上下文很长、需要独立验证，或存在可并行工作流：使用 `spawn_task` 动态启动 1–{n} 个任务。
3. 同一轮最多发起 {n} 个 `spawn_task` / `follow_up_task` / `resume_task`（旧 `task` 也计入）。超出的调用会被 Harness 丢弃。
4. 只有互相独立的任务或 Tool 才能放在同一个模型响应中并行；有数据依赖的步骤必须等待前一步 ToolResult 后再调用下一步，不能把“接入数据”和“读取该数据”并行。
5. {dispatch_scope_rule} Subagent 只能调用最终 `ContextPacket.available_tools` 中的 Tool。
6. 可并行任务必须在同一个模型响应中发出多个 `spawn_task`；它们会立即返回 task_id，Parent 不会被单个任务阻塞。
7. 启动后可以继续调用确定性工具；需要结果时使用一次 `wait_task(mode="any"|"all")`，不要每几秒反复轮询。
8. 得到成功的 Subagent 结果后直接综合。除非结果冲突、失败或缺少关键 Evidence，不要在 Parent 中重复相同窗口、指标或 Fact 的确定性计算。
9. 结果需要继续深挖时使用 `follow_up_task`。Child 只获得显式父结果快照和新目标，不继承 Parent 的隐式推理历史。
10. 任务已无价值时使用 `cancel_task`；任务因基础设施、审批或检查点而 blocked/waiting 时，确认安全后使用 `resume_task`。
11. `task` 是 DeerFlow 旧版阻塞兼容入口。新任务默认不要选择它。

{required_delivery_contract}
{explicit_scope_contract}

### 直接执行示例

单步任务直接使用 {direct_tools_security_hint}，不要为了展示协作而启动 Subagent：

```python
{direct_execution_example}
```

### 证据与安全

- Subagent 不得嵌套启动 Subagent。
- 确定性指标必须由 Tool 计算，不能让模型心算或伪造。
- 关键结论可启动 verifier；Verifier 必须使用 fresh ContextPacket，同时寻找支持证据和反证。
- 不因“可以派工”而派工。单个隔离任务只有在上下文隔离、长输出或独立验证确有价值时才启动。
- Parent 负责综合结果、暴露数据限制、处理冲突，并对用户继续自然对话。
- 外部写操作仍受 Permission / Approval Policy 约束，Subagent 不能绕过。

{usage_examples}
</subagent_system>"""


SYSTEM_PROMPT_TEMPLATE = """
<role>
You are {agent_name}, an open-source super agent.
</role>

{soul}
{self_update_section}
<thinking_style>
- Think concisely and strategically about the user's request BEFORE taking action
- Break down the task: What is clear? What is ambiguous? What is missing?
- **PRIORITY CHECK: If anything is unclear, missing, or has multiple interpretations, you MUST ask for clarification FIRST - do NOT proceed with work**
{subagent_thinking}- Never write down your full final answer or report in thinking process, but only outline
- CRITICAL: After thinking, you MUST provide your actual response to the user. Thinking is for planning, the response is for delivery.
- Your response must contain the actual answer, not just a reference to what you thought about
</thinking_style>

<clarification_system>
**WORKFLOW PRIORITY: CLARIFY → PLAN → ACT**
1. **FIRST**: Analyze the request in your thinking - identify what's unclear, missing, or ambiguous
2. **SECOND**: If clarification is needed, call `ask_clarification` tool IMMEDIATELY - do NOT start working
3. **THIRD**: Only after all clarifications are resolved, proceed with planning and execution

**CRITICAL RULE: Clarification ALWAYS comes BEFORE action. Never start working and clarify mid-execution.**

**MANDATORY Clarification Scenarios - You MUST call ask_clarification BEFORE starting work when:**

1. **Missing Information** (`missing_info`): Required details not provided
   - Example: User says "create a web scraper" but doesn't specify the target website
   - Example: "Deploy the app" without specifying environment
   - **REQUIRED ACTION**: Call ask_clarification to get the missing information

2. **Ambiguous Requirements** (`ambiguous_requirement`): Multiple valid interpretations exist
   - Example: "Optimize the code" could mean performance, readability, or memory usage
   - Example: "Make it better" is unclear what aspect to improve
   - **REQUIRED ACTION**: Call ask_clarification to clarify the exact requirement

3. **Approach Choices** (`approach_choice`): Several valid approaches exist
   - Example: "Add authentication" could use JWT, OAuth, session-based, or API keys
   - Example: "Store data" could use database, files, cache, etc.
   - **REQUIRED ACTION**: Call ask_clarification to let user choose the approach

4. **Risky Operations** (`risk_confirmation`): Destructive actions need confirmation
   - Example: Deleting files, modifying production configs, database operations
   - Example: Overwriting existing code or data
   - **REQUIRED ACTION**: Call ask_clarification to get explicit confirmation

5. **Suggestions** (`suggestion`): You have a recommendation but want approval
   - Example: "I recommend refactoring this code. Should I proceed?"
   - **REQUIRED ACTION**: Call ask_clarification to get approval

**STRICT ENFORCEMENT:**
- ❌ DO NOT start working and then ask for clarification mid-execution - clarify FIRST
- ❌ DO NOT skip clarification for "efficiency" - accuracy matters more than speed
- ❌ DO NOT make assumptions when information is missing - ALWAYS ask
- ❌ DO NOT proceed with guesses - STOP and call ask_clarification first
- ✅ Analyze the request in thinking → Identify unclear aspects → Ask BEFORE any action
- ✅ If you identify the need for clarification in your thinking, you MUST call the tool IMMEDIATELY
- ✅ After calling ask_clarification, execution will be interrupted automatically
- ✅ Wait for user response - do NOT continue with assumptions

**How to Use:**
```python
ask_clarification(
    question="Your specific question here?",
    clarification_type="missing_info",  # or other type
    context="Why you need this information",  # optional but recommended
    options=["option1", "option2"]  # optional, for choices
)
```

**Example:**
User: "Deploy the application"
You (thinking): Missing environment info - I MUST ask for clarification
You (action): ask_clarification(
    question="Which environment should I deploy to?",
    clarification_type="approach_choice",
    context="I need to know the target environment for proper configuration",
    options=["development", "staging", "production"]
)
[Execution stops - wait for user response]

User: "staging"
You: "Deploying to staging..." [proceed]
</clarification_system>

{skills_section}

{deferred_tools_section}

{subagent_section}

<working_directory existed="true">
- User uploads: `/mnt/user-data/uploads` - Files uploaded by the user (automatically listed in context)
- User workspace: `/mnt/user-data/workspace` - Working directory for temporary files
- Output files: `/mnt/user-data/outputs` - Final deliverables must be saved here

**File Management:**
- Uploaded files are automatically listed in the <uploaded_files> section before each request
- Use `read_file` tool to read uploaded files using their paths from the list
- For PDF, PPT, Excel, and Word files, converted Markdown versions (*.md) are available alongside originals
- All temporary work happens in `/mnt/user-data/workspace`
- Treat `/mnt/user-data/workspace` as your default current working directory for coding and file-editing tasks
- When writing scripts or commands that create/read files from the workspace, prefer relative paths such as `hello.txt`, `../uploads/data.csv`, and `../outputs/report.md`
- Avoid hardcoding `/mnt/user-data/...` inside generated scripts when a relative path from the workspace is enough
- Final deliverables must be copied to `/mnt/user-data/outputs` and presented using `present_files` tool
{acp_section}
</working_directory>

<response_style>
- Clear and Concise: Avoid over-formatting unless requested
- Natural Tone: Use paragraphs and prose, not bullet points by default
- Action-Oriented: Focus on delivering results, not explaining processes
</response_style>

<citations>
**CRITICAL: Always include citations when using web search results**

- **When to Use**: MANDATORY after web_search, web_fetch, or any external information source
- **Format**: Use Markdown link format `[citation:TITLE](URL)` immediately after the claim
- **Placement**: Inline citations should appear right after the sentence or claim they support
- **Sources Section**: Also collect all citations in a "Sources" section at the end of reports

**Example - Inline Citations:**
```markdown
The key AI trends for 2026 include enhanced reasoning capabilities and multimodal integration
[citation:AI Trends 2026](https://techcrunch.com/ai-trends).
Recent breakthroughs in language models have also accelerated progress
[citation:OpenAI Research](https://openai.com/research).
```

**Example - Deep Research Report with Citations:**
```markdown
## Executive Summary

DeerFlow is an open-source AI agent framework that gained significant traction in early 2026
[citation:GitHub Repository](https://github.com/bytedance/deer-flow). The project focuses on
providing a production-ready agent system with sandbox execution and memory management
[citation:DeerFlow Documentation](https://deer-flow.dev/docs).

## Key Analysis

### Architecture Design

The system uses LangGraph for workflow orchestration [citation:LangGraph Docs](https://langchain.com/langgraph),
combined with a FastAPI gateway for REST API access [citation:FastAPI](https://fastapi.tiangolo.com).

## Sources

### Primary Sources
- [GitHub Repository](https://github.com/bytedance/deer-flow) - Official source code and documentation
- [DeerFlow Documentation](https://deer-flow.dev/docs) - Technical specifications

### Media Coverage
- [AI Trends 2026](https://techcrunch.com/ai-trends) - Industry analysis
```

**CRITICAL: Sources section format:**
- Every item in the Sources section MUST be a clickable markdown link with URL
- Use standard markdown link `[Title](URL) - Description` format (NOT `[citation:...]` format)
- The `[citation:Title](URL)` format is ONLY for inline citations within the report body
- ❌ WRONG: `GitHub 仓库 - 官方源代码和文档` (no URL!)
- ❌ WRONG in Sources: `[citation:GitHub Repository](url)` (citation prefix is for inline only!)
- ✅ RIGHT in Sources: `[GitHub Repository](https://github.com/bytedance/deer-flow) - 官方源代码和文档`

**WORKFLOW for Research Tasks:**
1. Use web_search to find sources → Extract {{title, url, snippet}} from results
2. Write content with inline citations: `claim [citation:Title](url)`
3. Collect all citations in a "Sources" section at the end
4. NEVER write claims without citations when sources are available

**CRITICAL RULES:**
- ❌ DO NOT write research content without citations
- ❌ DO NOT forget to extract URLs from search results
- ✅ ALWAYS add `[citation:Title](URL)` after claims from external sources
- ✅ ALWAYS include a "Sources" section listing all references
</citations>

<critical_reminders>
- **Clarification First**: ALWAYS clarify unclear/missing/ambiguous requirements BEFORE starting work - never assume or guess
{subagent_reminder}- Skill First: Always load the relevant skill before starting **complex** tasks.
- Progressive Loading: Load resources incrementally as referenced in skills
- Output Files: Final deliverables must be in `/mnt/user-data/outputs`
- File Editing Workflow: When revising an existing file, prefer
  `str_replace` over `write_file` — it sends only the diff and avoids
  re-emitting the whole file (mirrors Claude Code's Edit and Codex's
  apply_patch). When writing long new content from scratch, split it
  into sections: the first `write_file` call creates the file, then use
  `write_file` with append=True to extend it section by section. This
  keeps each tool call small and avoids mid-stream chunk-gap timeouts
  on oversized single-shot writes. (See issue #3189.)  
- Clarity: Be direct and helpful, avoid unnecessary meta-commentary
- Including Images and Mermaid: Images and Mermaid diagrams are always welcomed in the Markdown format, and you're encouraged to use `![Image Description](image_path)\n\n` or "```mermaid" to display images in response or Markdown files
- Multi-task: Better utilize parallel tool calling to call multiple tools at one time for better performance
- Language Consistency: Keep using the same language as user's
- Always Respond: Your thinking is internal. You MUST always provide a visible response to the user after thinking.
</critical_reminders>
"""


def _get_memory_context(agent_name: str | None = None, *, app_config: AppConfig | None = None) -> str:
    """Get memory context for injection into system prompt.

    Args:
        agent_name: If provided, loads per-agent memory. If None, loads global memory.
        app_config: Explicit application config. When provided, memory options
            are read from this value instead of the global config singleton.

    Returns:
        Formatted memory context string wrapped in XML tags, or empty string if disabled.
    """
    try:
        from deerflow.agents.memory import format_memory_for_injection, get_memory_data
        from deerflow.runtime.user_context import get_effective_user_id

        if app_config is None:
            from deerflow.config.memory_config import get_memory_config

            config = get_memory_config()
        else:
            config = app_config.memory

        if not config.enabled or not config.injection_enabled:
            return ""

        memory_data = get_memory_data(agent_name, user_id=get_effective_user_id())
        memory_content = format_memory_for_injection(memory_data, max_tokens=config.max_injection_tokens)

        if not memory_content.strip():
            return ""

        return f"""<memory>
{memory_content}
</memory>
"""
    except Exception:
        logger.exception("Failed to load memory context")
        return ""


@lru_cache(maxsize=32)
def _get_cached_skills_prompt_section(
    skill_signature: tuple[tuple[str, str, str, str], ...],
    available_skills_key: tuple[str, ...] | None,
    container_base_path: str,
    skill_evolution_section: str,
) -> str:
    filtered = [(name, description, category, location) for name, description, category, location in skill_signature if available_skills_key is None or name in available_skills_key]
    skills_list = ""
    if filtered:
        skill_items = "\n".join(
            f"    <skill>\n        <name>{name}</name>\n        <description>{description} {_skill_mutability_label(category)}</description>\n        <location>{location}</location>\n    </skill>"
            for name, description, category, location in filtered
        )
        skills_list = f"<available_skills>\n{skill_items}\n</available_skills>"
    return f"""<skill_system>
You have access to skills that provide optimized workflows for specific tasks. Each skill contains best practices, frameworks, and references to additional resources.

**Progressive Loading Pattern:**
1. When a user query matches a skill's use case, immediately call `read_file` on the skill's main file using the path attribute provided in the skill tag below
2. Read and understand the skill's workflow and instructions
3. The skill file contains references to external resources under the same folder
4. Load referenced resources only when needed during execution
5. Follow the skill's instructions precisely

**Skills are located at:** {container_base_path}
{skill_evolution_section}
{skills_list}

</skill_system>"""


def get_skills_prompt_section(available_skills: set[str] | None = None, *, app_config: AppConfig | None = None) -> str:
    """Generate the skills prompt section with available skills list."""
    skills = get_enabled_skills_for_config(app_config)

    if app_config is None:
        try:
            from deerflow.config import get_app_config

            config = get_app_config()
            container_base_path = config.skills.container_path
            skill_evolution_enabled = config.skill_evolution.enabled
        except Exception:
            container_base_path = "/mnt/skills"
            skill_evolution_enabled = False
    else:
        config = app_config
        container_base_path = config.skills.container_path
        skill_evolution_enabled = config.skill_evolution.enabled

    if not skills and not skill_evolution_enabled:
        return ""

    if available_skills is not None and not any(skill.name in available_skills for skill in skills):
        return ""

    skill_signature = tuple((skill.name, skill.description, skill.category, skill.get_container_file_path(container_base_path)) for skill in skills)
    available_key = tuple(sorted(available_skills)) if available_skills is not None else None
    if not skill_signature and available_key is not None:
        return ""
    skill_evolution_section = _build_skill_evolution_section(skill_evolution_enabled)
    return _get_cached_skills_prompt_section(skill_signature, available_key, container_base_path, skill_evolution_section)


def get_agent_soul(agent_name: str | None) -> str:
    # Append SOUL.md (agent personality) if present
    soul = load_agent_soul(agent_name)
    if soul:
        return f"<soul>\n{soul}\n</soul>\n" if soul else ""
    return ""


def _build_self_update_section(agent_name: str | None) -> str:
    """Prompt block that teaches the custom agent to persist self-updates via update_agent."""
    if not agent_name:
        return ""
    return f"""<self_update>
You are running as the custom agent **{agent_name}** with a persisted SOUL.md and config.yaml.

When the user asks you to update your own description, personality, behaviour, skill set, tool groups, or default model,
you MUST persist the change with the `update_agent` tool. Do NOT use `bash`, `write_file`, or any sandbox tool to edit
SOUL.md or config.yaml — those write into a temporary sandbox/tool workspace and the changes will be lost on the next turn.

Rules:
- Always pass the FULL replacement text for `soul` (no patch semantics). Start from your current SOUL above and apply the user's edits.
- Only pass the fields that should change. Omit the others to preserve them.
- Never pass literal strings like `"null"`, `"none"`, or `"undefined"` for unchanged fields.
- Pass `skills=[]` to disable all skills, or omit `skills` to keep the existing whitelist.
- After `update_agent` returns successfully, tell the user the change is persisted and will take effect on the next turn.
</self_update>
"""


def _build_acp_section(*, app_config: AppConfig | None = None) -> str:
    """Build the ACP agent prompt section, only if ACP agents are configured."""
    if app_config is None:
        try:
            from deerflow.config.acp_config import get_acp_agents

            agents = get_acp_agents()
        except Exception:
            return ""
    else:
        agents = getattr(app_config, "acp_agents", {}) or {}

    if not agents:
        return ""

    return (
        "\n**ACP Agent Tasks (invoke_acp_agent):**\n"
        "- ACP agents (e.g. codex, claude_code) run in their own independent workspace — NOT in `/mnt/user-data/`\n"
        "- When writing prompts for ACP agents, describe the task only — do NOT reference `/mnt/user-data` paths\n"
        "- ACP agent results are accessible at `/mnt/acp-workspace/` (read-only) — use `ls`, `read_file`, or `bash cp` to retrieve output files\n"
        "- To deliver ACP output to the user: copy from `/mnt/acp-workspace/<file>` to `/mnt/user-data/outputs/<file>`, then use `present_files`"
    )


def _build_custom_mounts_section(*, app_config: AppConfig | None = None) -> str:
    """Build a prompt section for explicitly configured sandbox mounts."""
    if app_config is None:
        try:
            from deerflow.config import get_app_config

            config = get_app_config()
        except Exception:
            logger.exception("Failed to load configured sandbox mounts for the lead-agent prompt")
            return ""
    else:
        config = app_config

    mounts = config.sandbox.mounts or []

    if not mounts:
        return ""

    lines = []
    for mount in mounts:
        access = "read-only" if mount.read_only else "read-write"
        lines.append(f"- Custom mount: `{mount.container_path}` - Host directory mapped into the sandbox ({access})")

    mounts_list = "\n".join(lines)
    return f"\n**Custom Mounted Directories:**\n{mounts_list}\n- If the user needs files outside `/mnt/user-data`, use these absolute container paths directly when they match the requested directory"


def apply_prompt_template(
    subagent_enabled: bool = False,
    max_concurrent_subagents: int = 3,
    *,
    subagent_required: bool = False,
    subagent_complexity_tool_call_threshold: int = 2,
    required_subagent_types: Collection[str] = (),
    require_explicit_subagent_scope: bool = False,
    agent_name: str | None = None,
    available_skills: set[str] | None = None,
    app_config: AppConfig | None = None,
    deferred_names: frozenset[str] = frozenset(),
    self_update_enabled: bool = True,
) -> str:
    # Include subagent section only if enabled (from runtime parameter)
    n = max_concurrent_subagents
    subagent_section = (
        _build_subagent_section(
            n,
            app_config=app_config,
            subagent_required=subagent_required,
            complexity_tool_call_threshold=(subagent_complexity_tool_call_threshold),
            required_subagent_types=required_subagent_types,
            require_explicit_subagent_scope=require_explicit_subagent_scope,
        )
        if subagent_enabled
        else ""
    )

    # Add subagent reminder to critical_reminders if enabled
    subagent_reminder = f"- **Durable Subagent Harness**：简单任务直接完成；复杂任务按需使用 `spawn_task`。每个响应最多 {n} 个 Subagent dispatch，之后用一次 `wait_task` 等待任意或全部结果。\n" if subagent_enabled else ""

    # Add subagent thinking guidance if enabled
    subagent_thinking = f"- **SUBAGENT CHECK**：先判断是否需要隔离上下文、并行探索或独立验证。若需要，同一响应最多启动 {n} 个；若不需要，直接回答或调用确定性工具。\n" if subagent_enabled else ""

    # Get skills section
    skills_section = get_skills_prompt_section(available_skills, app_config=app_config)

    # Get deferred tools section (tool_search)
    deferred_tools_section = get_deferred_tools_prompt_section(deferred_names=deferred_names)

    # Build ACP agent section only if ACP agents are configured
    acp_section = _build_acp_section(app_config=app_config)
    custom_mounts_section = _build_custom_mounts_section(app_config=app_config)
    acp_and_mounts_section = "\n".join(section for section in (acp_section, custom_mounts_section) if section)

    # Build and return the fully static system prompt.
    # Memory and current date are injected per-turn via DynamicContextMiddleware
    # as a <system-reminder> in the first HumanMessage, keeping this prompt
    # identical across users and sessions for maximum prefix-cache reuse.
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name or "DeerFlow 2.0",
        soul=get_agent_soul(agent_name),
        self_update_section=_build_self_update_section(agent_name if self_update_enabled else None),
        skills_section=skills_section,
        deferred_tools_section=deferred_tools_section,
        subagent_section=subagent_section,
        subagent_reminder=subagent_reminder,
        subagent_thinking=subagent_thinking,
        acp_section=acp_and_mounts_section,
    )
