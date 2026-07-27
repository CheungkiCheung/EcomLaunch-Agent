from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ToolGroupConfig(BaseModel):
    """Config section for a tool group"""

    name: str = Field(..., description="Unique name for the tool group")
    model_config = ConfigDict(extra="allow")


class ToolConfig(BaseModel):
    """Config section for a tool"""

    name: str = Field(..., description="Unique name for the tool")
    group: str = Field(..., description="Group name for the tool")
    use: str = Field(
        ...,
        description="Variable name of the tool provider(e.g. deerflow.sandbox.tools:bash_tool)",
    )
    default_enabled: bool = Field(
        default=True,
        description="Whether the tool is visible when an Agent does not request explicit tool groups",
    )
    enabled_if_env: str | None = Field(
        default=None,
        description="Optional environment feature flag that must be truthy before the tool can be loaded",
    )
    model_config = ConfigDict(extra="allow")
