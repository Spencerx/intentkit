"""LLM Call Logger Module.

Simple conversation tracking for project-based agent generation.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .utils import generate_request_id

logger = logging.getLogger(__name__)

# In-memory storage for conversation history
_conversation_history: Dict[str, List[Dict[str, str]]] = {}


class LLMLogger:
    """Simple logger for tracking conversation history per project."""

    def __init__(self, request_id: str, user_id: Optional[str] = None):
        """Initialize the LLM logger.

        Args:
            request_id: Unique request ID that groups related conversations
            user_id: Optional user ID for the request
        """
        self.request_id = request_id
        self.user_id = user_id

    @asynccontextmanager
    async def log_call(
        self,
        call_type: str,
        prompt: str,
        retry_count: int = 0,
        is_update: bool = False,
        existing_agent_id: Optional[str] = None,
        llm_model: Optional[str] = None,
        openai_messages: Optional[List[Dict[str, Any]]] = None,
    ):
        """Context manager for logging an LLM call (simplified for conversation tracking).

        Args:
            call_type: Type of LLM call (e.g., 'agent_generation')
            prompt: The original prompt for this generation request
            retry_count: Retry attempt number (0 for initial, 1+ for retries)
            is_update: Whether this is an update operation
            existing_agent_id: ID of existing agent if update
            llm_model: LLM model being used
            openai_messages: Messages being sent to OpenAI

        Yields:
            Simple dict for tracking this call
        """
        call_info = {
            "type": call_type,
            "prompt": prompt,
            "request_id": self.request_id,
            "retry_count": retry_count,
        }

        logger.info(
            f"Started LLM call: {call_type} (request_id={self.request_id}, retry={retry_count})"
        )

        try:
            yield call_info
        except Exception as e:
            logger.error(
                f"LLM call failed: {call_type} (request_id={self.request_id}): {str(e)}"
            )
            raise

    async def log_successful_call(
        self,
        call_log: Dict[str, Any],
        response: Any,
        generated_content: Optional[Dict[str, Any]] = None,
        openai_messages: Optional[List[Dict[str, Any]]] = None,
        call_start_time: Optional[float] = None,
    ):
        """Log a successful LLM call completion.

        Args:
            call_log: The call log dict to update
            response: OpenAI API response
            generated_content: The generated content from the call
            openai_messages: Messages sent to OpenAI
            call_start_time: When the call started (for duration calculation)
        """
        logger.info(
            f"LLM call completed successfully: {call_log.get('type', 'unknown')}"
        )

        # Store conversation in memory for this project
        if generated_content and self.request_id:
            self._store_conversation_turn(
                prompt=call_log.get("prompt", ""),
                response_content=generated_content,
                call_type=call_log.get("type", ""),
            )

    def _store_conversation_turn(
        self, prompt: str, response_content: Dict[str, Any], call_type: str
    ):
        """Store a conversation turn in memory."""
        if self.request_id not in _conversation_history:
            _conversation_history[self.request_id] = []

        # Add user message
        _conversation_history[self.request_id].append(
            {"role": "user", "content": prompt}
        )

        # Add AI response based on call type
        ai_content = self._format_ai_response(response_content, call_type)
        if ai_content:
            _conversation_history[self.request_id].append(
                {"role": "assistant", "content": ai_content}
            )

    def _format_ai_response(
        self, content: Dict[str, Any], call_type: str
    ) -> Optional[str]:
        """Format AI response content for conversation history."""
        if call_type == "agent_attribute_generation" and "attributes" in content:
            attrs = content["attributes"]
            response = "I've created an agent with the following attributes:\n"
            response += f"Name: {attrs.get('name', 'N/A')}\n"
            response += f"Purpose: {attrs.get('purpose', 'N/A')}\n"
            response += f"Personality: {attrs.get('personality', 'N/A')}\n"
            response += f"Principles: {attrs.get('principles', 'N/A')}"
            return response

        elif call_type == "agent_attribute_update" and "updated_attributes" in content:
            updates = content["updated_attributes"]
            response = "I've updated the agent with the following changes:\n"
            for attr, value in updates.items():
                if value:
                    response += f"{attr.title()}: {value}\n"
            return response

        elif call_type == "schema_error_correction":
            return "I've corrected the agent schema to fix validation errors."

        return None


def create_llm_logger(user_id: Optional[str] = None) -> LLMLogger:
    """Create a new LLM logger with a unique request ID.

    Args:
        user_id: Optional user ID for the request

    Returns:
        LLMLogger instance with unique request ID
    """
    request_id = generate_request_id()
    return LLMLogger(request_id=request_id, user_id=user_id)


async def get_conversation_history(
    project_id: str,
    user_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Get conversation history for a project from memory.

    Args:
        project_id: Project/request ID to get history for
        user_id: Optional user ID for additional filtering

    Returns:
        List of conversation messages in chronological order
    """
    logger.info(f"Getting conversation history for project: {project_id}")

    history = _conversation_history.get(project_id, [])
    logger.info(f"Found {len(history)} conversation messages for project {project_id}")

    return history
