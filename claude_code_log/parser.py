#!/usr/bin/env python3
"""Parse and extract data from Claude transcript JSONL files."""

import json
from pathlib import Path
import re
from typing import Any, List, Optional, Union, TYPE_CHECKING, Dict, cast
from datetime import datetime
import dateparser

from .models import (
    TranscriptEntry,
    SummaryTranscriptEntry,
    ContentItem,
    TextContent,
    ThinkingContent,
    UserTranscriptEntry,
    AssistantTranscriptEntry,
    SystemTranscriptEntry,
    UsageInfo,
    ToolUseContent,
    ToolResultContent,
    ImageContent,
)

from anthropic.types import Message as AnthropicMessage
from anthropic.types import Usage as AnthropicUsage

if TYPE_CHECKING:
    from .cache import CacheManager


def extract_text_content(content: Union[str, List[ContentItem], None]) -> str:
    """Extract text content from Claude message content structure (supports both custom and Anthropic types)."""
    if content is None:
        return ""
    if isinstance(content, list):
        text_parts: List[str] = []
        for item in content:
            # Handle both custom TextContent and official Anthropic TextBlock
            if isinstance(item, TextContent):
                text_parts.append(item.text)
            elif (
                hasattr(item, "type")
                and hasattr(item, "text")
                and getattr(item, "type") == "text"
            ):
                # Official Anthropic TextBlock
                text_parts.append(getattr(item, "text"))
            elif isinstance(item, ThinkingContent):
                # Skip thinking content in main text extraction
                continue
            elif hasattr(item, "type") and getattr(item, "type") == "thinking":
                # Skip official Anthropic thinking content too
                continue
        return "\n".join(text_parts)
    else:
        return str(content) if content else ""


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO timestamp to datetime object."""
    try:
        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def filter_messages_by_date(
    messages: List[TranscriptEntry], from_date: Optional[str], to_date: Optional[str]
) -> List[TranscriptEntry]:
    """Filter messages based on date range."""
    if not from_date and not to_date:
        return messages

    # Parse the date strings using dateparser
    from_dt = None
    to_dt = None

    if from_date:
        from_dt = dateparser.parse(from_date)
        if not from_dt:
            raise ValueError(f"Could not parse from-date: {from_date}")
        # If parsing relative dates like "today", start from beginning of day
        if from_date in ["today", "yesterday"] or "days ago" in from_date:
            from_dt = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    if to_date:
        to_dt = dateparser.parse(to_date)
        if not to_dt:
            raise ValueError(f"Could not parse to-date: {to_date}")
        # If parsing relative dates like "today", end at end of day
        if to_date in ["today", "yesterday"] or "days ago" in to_date:
            to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    filtered_messages: List[TranscriptEntry] = []
    for message in messages:
        # Handle SummaryTranscriptEntry which doesn't have timestamp
        if isinstance(message, SummaryTranscriptEntry):
            filtered_messages.append(message)
            continue

        timestamp_str = message.timestamp
        if not timestamp_str:
            continue

        message_dt = parse_timestamp(timestamp_str)
        if not message_dt:
            continue

        # Convert to naive datetime for comparison (dateparser returns naive datetimes)
        if message_dt.tzinfo:
            message_dt = message_dt.replace(tzinfo=None)

        # Check if message falls within date range
        if from_dt and message_dt < from_dt:
            continue
        if to_dt and message_dt > to_dt:
            continue

        filtered_messages.append(message)

    return filtered_messages


def load_transcript(
    jsonl_path: Path,
    cache_manager: Optional["CacheManager"] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    silent: bool = False,
) -> List[TranscriptEntry]:
    """Load and parse JSONL transcript file, using cache if available."""
    # Try to load from cache first
    if cache_manager is not None:
        # Use filtered loading if date parameters are provided
        if from_date or to_date:
            cached_entries = cache_manager.load_cached_entries_filtered(
                jsonl_path, from_date, to_date
            )
        else:
            cached_entries = cache_manager.load_cached_entries(jsonl_path)

        if cached_entries is not None:
            if not silent:
                print(f"Loading {jsonl_path} from cache...")
            return cached_entries

    # Parse from source file
    messages: List[TranscriptEntry] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        if not silent:
            print(f"Processing {jsonl_path}...")
        for line_no, line in enumerate(f):
            line = line.strip()
            if line:
                try:
                    entry_dict: dict[str, Any] | str = json.loads(line)
                    if not isinstance(entry_dict, dict):
                        print(
                            f"Line {line_no} of {jsonl_path} is not a JSON object: {line}"
                        )
                        continue

                    entry_type: str | None = entry_dict.get("type")

                    if entry_type in ["user", "assistant", "summary", "system"]:
                        # Parse using Pydantic models
                        entry = parse_transcript_entry(entry_dict)
                        messages.append(entry)
                    else:
                        print(
                            f"Line {line_no} of {jsonl_path} is not a recognised message type: {line}"
                        )
                except json.JSONDecodeError as e:
                    print(
                        f"Line {line_no} of {jsonl_path} | JSON decode error: {str(e)}"
                    )
                except ValueError as e:
                    # Extract a more descriptive error message
                    error_msg = str(e)
                    if "validation error" in error_msg.lower():
                        err_no_url = re.sub(
                            r"    For further information visit https://errors.pydantic(.*)\n?",
                            "",
                            error_msg,
                        )
                        print(f"Line {line_no} of {jsonl_path} | {err_no_url}")
                    else:
                        print(
                            f"Line {line_no} of {jsonl_path} | ValueError: {error_msg}"
                            "\n{traceback.format_exc()}"
                        )
                except Exception as e:
                    print(
                        f"Line {line_no} of {jsonl_path} | Unexpected error: {str(e)}"
                        "\n{traceback.format_exc()}"
                    )

    # Save to cache if cache manager is available
    if cache_manager is not None:
        cache_manager.save_cached_entries(jsonl_path, messages)

    return messages


def load_directory_transcripts(
    directory_path: Path,
    cache_manager: Optional["CacheManager"] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    silent: bool = False,
) -> List[TranscriptEntry]:
    """Load all JSONL transcript files from a directory and combine them."""
    all_messages: List[TranscriptEntry] = []

    # Find all .jsonl files
    jsonl_files = list(directory_path.glob("*.jsonl"))

    for jsonl_file in jsonl_files:
        messages = load_transcript(
            jsonl_file, cache_manager, from_date, to_date, silent
        )
        all_messages.extend(messages)

    # Sort all messages chronologically
    def get_timestamp(entry: TranscriptEntry) -> str:
        if hasattr(entry, "timestamp"):
            return entry.timestamp  # type: ignore
        return ""

    all_messages.sort(key=get_timestamp)
    return all_messages


def normalize_usage_info(usage_data: Any) -> Optional[UsageInfo]:
    """Normalize usage data to be compatible with both custom and Anthropic formats."""
    if usage_data is None:
        return None

    # If it's already a UsageInfo instance, return as-is
    if isinstance(usage_data, UsageInfo):
        return usage_data

    # If it's an Anthropic Usage instance, convert using our method
    if isinstance(usage_data, AnthropicUsage):
        return UsageInfo.from_anthropic_usage(usage_data)

    # If it has the shape of an Anthropic Usage, try to construct it first
    if hasattr(usage_data, "input_tokens") and hasattr(usage_data, "output_tokens"):
        try:
            # Try to create an Anthropic Usage first
            anthropic_usage = AnthropicUsage.model_validate(usage_data)
            return UsageInfo.from_anthropic_usage(anthropic_usage)
        except Exception:
            # Fall back to direct conversion
            return UsageInfo(
                input_tokens=getattr(usage_data, "input_tokens", None),
                cache_creation_input_tokens=getattr(
                    usage_data, "cache_creation_input_tokens", None
                ),
                cache_read_input_tokens=getattr(
                    usage_data, "cache_read_input_tokens", None
                ),
                output_tokens=getattr(usage_data, "output_tokens", None),
                service_tier=getattr(usage_data, "service_tier", None),
                server_tool_use=getattr(usage_data, "server_tool_use", None),
            )

    # If it's a dict, validate and convert to our format
    if isinstance(usage_data, dict):
        return UsageInfo.model_validate(usage_data)

    return None


def parse_content_item(item_data: Dict[str, Any]) -> ContentItem:
    """Parse a content item using enhanced approach with Anthropic types."""
    try:
        content_type = item_data.get("type", "")

        # Try official Anthropic types first for better future compatibility
        if content_type == "text":
            try:
                from anthropic.types.text_block import TextBlock

                return TextBlock.model_validate(item_data)
            except Exception:
                return TextContent.model_validate(item_data)
        elif content_type == "tool_use":
            try:
                from anthropic.types.tool_use_block import ToolUseBlock

                return ToolUseBlock.model_validate(item_data)
            except Exception:
                return ToolUseContent.model_validate(item_data)
        elif content_type == "thinking":
            try:
                from anthropic.types.thinking_block import ThinkingBlock

                return ThinkingBlock.model_validate(item_data)
            except Exception:
                return ThinkingContent.model_validate(item_data)
        elif content_type == "tool_result":
            return ToolResultContent.model_validate(item_data)
        elif content_type == "image":
            return ImageContent.model_validate(item_data)
        else:
            # Fallback to text content for unknown types
            return TextContent(type="text", text=str(item_data))
    except Exception:
        return TextContent(type="text", text=str(item_data))


def parse_message_content(content_data: Any) -> Union[str, List[ContentItem]]:
    """Parse message content, handling both string and list formats."""
    if isinstance(content_data, str):
        return content_data
    elif isinstance(content_data, list):
        content_list = cast(List[Dict[str, Any]], content_data)
        return [parse_content_item(item) for item in content_list]
    else:
        return str(content_data)


def parse_transcript_entry(data: Dict[str, Any]) -> TranscriptEntry:
    """
    Parse a JSON dictionary into the appropriate TranscriptEntry type.

    Enhanced to optionally use official Anthropic types for assistant messages.

    Args:
        data: Dictionary parsed from JSON

    Returns:
        The appropriate TranscriptEntry subclass

    Raises:
        ValueError: If the data doesn't match any known transcript entry type
    """
    entry_type = data.get("type")

    if entry_type == "user":
        # Parse message content if present
        data_copy = data.copy()
        if "message" in data_copy and "content" in data_copy["message"]:
            data_copy["message"] = data_copy["message"].copy()
            data_copy["message"]["content"] = parse_message_content(
                data_copy["message"]["content"]
            )
        # Parse toolUseResult if present and it's a list of content items
        if "toolUseResult" in data_copy and isinstance(
            data_copy["toolUseResult"], list
        ):
            # Check if it's a list of content items (MCP tool results)
            tool_use_result = cast(List[Any], data_copy["toolUseResult"])
            if (
                tool_use_result
                and isinstance(tool_use_result[0], dict)
                and "type" in tool_use_result[0]
            ):
                data_copy["toolUseResult"] = [
                    parse_content_item(cast(Dict[str, Any], item))
                    for item in tool_use_result
                    if isinstance(item, dict)
                ]
        return UserTranscriptEntry.model_validate(data_copy)

    elif entry_type == "assistant":
        # Enhanced assistant message parsing with optional Anthropic types
        data_copy = data.copy()

        # Validate compatibility with official Anthropic Message type
        if "message" in data_copy:
            try:
                message_data = data_copy["message"]
                AnthropicMessage.model_validate(message_data)
                # Successfully validated - our data is compatible with official Anthropic types
            except Exception:
                # Validation failed - continue with standard parsing
                pass

        # Standard parsing path (works for all cases)
        if "message" in data_copy and "content" in data_copy["message"]:
            message_copy = data_copy["message"].copy()
            message_copy["content"] = parse_message_content(message_copy["content"])

            # Normalize usage data to support both Anthropic and custom formats
            if "usage" in message_copy:
                message_copy["usage"] = normalize_usage_info(message_copy["usage"])

            data_copy["message"] = message_copy
        return AssistantTranscriptEntry.model_validate(data_copy)

    elif entry_type == "summary":
        return SummaryTranscriptEntry.model_validate(data)

    elif entry_type == "system":
        return SystemTranscriptEntry.model_validate(data)

    else:
        raise ValueError(f"Unknown transcript entry type: {entry_type}")
