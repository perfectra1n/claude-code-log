"""Pydantic models for Claude Code transcript JSON structures.

Enhanced to leverage official Anthropic types where beneficial.
"""

from typing import Any, List, Union, Optional, Dict, Literal
from pydantic import BaseModel

from anthropic.types import Message as AnthropicMessage
from anthropic.types import StopReason
from anthropic.types import Usage as AnthropicUsage
from anthropic.types.content_block import ContentBlock


class TodoItem(BaseModel):
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed"]
    priority: Literal["high", "medium", "low"]


class UsageInfo(BaseModel):
    """Token usage information that extends Anthropic's Usage type to handle optional fields."""

    input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    service_tier: Optional[str] = None
    server_tool_use: Optional[Dict[str, Any]] = None

    def to_anthropic_usage(self) -> Optional[AnthropicUsage]:
        """Convert to Anthropic Usage type if both required fields are present."""
        if self.input_tokens is not None and self.output_tokens is not None:
            return AnthropicUsage(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                cache_creation_input_tokens=self.cache_creation_input_tokens,
                cache_read_input_tokens=self.cache_read_input_tokens,
                service_tier=self.service_tier,  # type: ignore
                server_tool_use=self.server_tool_use,  # type: ignore
            )
        return None

    @classmethod
    def from_anthropic_usage(cls, usage: AnthropicUsage) -> "UsageInfo":
        """Create UsageInfo from Anthropic Usage."""
        return cls(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens,
            service_tier=usage.service_tier,
            server_tool_use=usage.server_tool_use.model_dump()
            if usage.server_tool_use
            else None,
        )


class TextContent(BaseModel):
    type: Literal["text"]
    text: str


class ToolUseContent(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    type: Literal["tool_result"]
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]]]
    is_error: Optional[bool] = None


class ThinkingContent(BaseModel):
    type: Literal["thinking"]
    thinking: str
    signature: Optional[str] = None


class ImageSource(BaseModel):
    type: Literal["base64"]
    media_type: str
    data: str


class ImageContent(BaseModel):
    type: Literal["image"]
    source: ImageSource


# Enhanced ContentItem to include official Anthropic ContentBlock types
ContentItem = Union[
    TextContent,
    ToolUseContent,
    ToolResultContent,
    ThinkingContent,
    ImageContent,
    ContentBlock,  # Official Anthropic content block types
]


class UserMessage(BaseModel):
    role: Literal["user"]
    content: Union[str, List[ContentItem]]


class AssistantMessage(BaseModel):
    """Assistant message model compatible with Anthropic's Message type."""

    id: str
    type: Literal["message"]
    role: Literal["assistant"]
    model: str
    content: List[ContentItem]
    stop_reason: Optional[StopReason] = None
    stop_sequence: Optional[str] = None
    usage: Optional[UsageInfo] = None

    @classmethod
    def from_anthropic_message(
        cls, anthropic_msg: AnthropicMessage
    ) -> "AssistantMessage":
        """Create AssistantMessage from official Anthropic Message."""
        # Convert Anthropic Message to our format, preserving official types where possible
        return cls(
            id=anthropic_msg.id,
            type=anthropic_msg.type,
            role=anthropic_msg.role,
            model=anthropic_msg.model,
            content=list(
                anthropic_msg.content
            ),  # Convert to list for ContentItem compatibility
            stop_reason=anthropic_msg.stop_reason,
            stop_sequence=anthropic_msg.stop_sequence,
            usage=UsageInfo.from_anthropic_usage(anthropic_msg.usage)
            if anthropic_msg.usage
            else None,
        )


class FileInfo(BaseModel):
    filePath: str
    content: str
    numLines: int
    startLine: int
    totalLines: int


class FileReadResult(BaseModel):
    type: Literal["text"]
    file: FileInfo


class CommandResult(BaseModel):
    stdout: str
    stderr: str
    interrupted: bool
    isImage: bool


class TodoResult(BaseModel):
    oldTodos: List[TodoItem]
    newTodos: List[TodoItem]


class EditResult(BaseModel):
    oldString: Optional[str] = None
    newString: Optional[str] = None
    replaceAll: Optional[bool] = None
    originalFile: Optional[str] = None
    structuredPatch: Optional[Any] = None
    userModified: Optional[bool] = None


ToolUseResult = Union[
    str,
    List[TodoItem],
    FileReadResult,
    CommandResult,
    TodoResult,
    EditResult,
    List[ContentItem],
]


class BaseTranscriptEntry(BaseModel):
    parentUuid: Optional[str]
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    uuid: str
    timestamp: str
    isMeta: Optional[bool] = None


class UserTranscriptEntry(BaseTranscriptEntry):
    type: Literal["user"]
    message: UserMessage
    toolUseResult: Optional[ToolUseResult] = None


class AssistantTranscriptEntry(BaseTranscriptEntry):
    type: Literal["assistant"]
    message: AssistantMessage
    requestId: Optional[str] = None


class SummaryTranscriptEntry(BaseModel):
    type: Literal["summary"]
    summary: str
    leafUuid: str
    cwd: Optional[str] = None


class SystemTranscriptEntry(BaseTranscriptEntry):
    """System messages like warnings, notifications, etc."""

    type: Literal["system"]
    content: str
    level: Optional[str] = None  # e.g., "warning", "info", "error"


TranscriptEntry = Union[
    UserTranscriptEntry,
    AssistantTranscriptEntry,
    SummaryTranscriptEntry,
    SystemTranscriptEntry,
]
