import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, TypeVar

import ollama
from loguru import logger
from ollama._types import ChatResponse, Message, Options
from pydantic import BaseModel, ValidationError
from PyQt6.QtCore import pyqtSignal
from typing_extensions import TypedDict

from snipai.src.common.utils import download_ollama_model
from snipai.src.services.base import BaseService

DEFAULT_KEEP_ALIVE = 60 * 60


class LLMRequest(TypedDict):
    id: str
    messages: Sequence[Message]
    stream: bool = False
    options: Options = {
        "num_gpu": -1,
        "temperature": 0.0,
        "seed": 42,
        "num_ctx": 1024,
        "frequency_penalty": 0.7,
    }


T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    task_id: str
    message: str
    is_json: bool = False

    @property
    def response(self) -> Dict[Any, Any] | str:
        """Return the message as a dictionary if it's JSON, otherwise return the message itself."""
        if self.is_json:
            return json.loads(self.message)
        return self.message


class LLMService(BaseService):
    chunk_received = pyqtSignal(str, str)  # task_id, content
    generation_completed = pyqtSignal(LLMResponse)  # task_id, content
    error_occurred = pyqtSignal(str, str)  # task_id, error_message

    def __init__(
        self, model: str, response_format: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.model = model
        download_ollama_model(self.model)
        self._active_tasks = {}
        self.response_format = response_format
        self.start()
        logger.info("LLM Service initialized")

    def with_structured_output(
        self, model: type[T] | Dict[str, Any]
    ) -> "LLMService":
        """
        Create a new LLM service instance with structured output capability.

        Args:
            model: A Pydantic BaseModel class or JSON schema that
            defines the expected structure

        Returns:
            LLMService: A new service instance configured for structured output
        """
        if isinstance(model, BaseModel):
            return LLMService(
                self.model, response_format=model.model_json_schema()
            )
        return LLMService(self.model, response_format=model)

    def _parse_structured_output(self, content: str):
        if not self.response_format:
            raise ValueError("No response format configured")

        try:
            # Try to parse the content as JSON first
            json_content = json.loads(content)
            # Then validate it against the Pydantic model
            validated_model = self.response_format.model_validate(json_content)
            # Return the validated JSON string
            return validated_model.model_dump_json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM output: {str(e)}")
            raise ValueError(f"Invalid JSON in LLM output: {content}")
        except ValidationError as e:
            logger.error(f"Failed to validate structured output: {str(e)}")
            raise ValueError(
                f"Output doesn't match expected structure: {content}"
            )

    def generate_response(
        self,
        messages: Sequence[Message],
        stream: bool = False,
        options: Optional[Options] = None,
        task_id: str = None,
    ) -> str:
        try:
            options = options or {
                "num_gpu": -1,
                "temperature": 0.0,
                "seed": 42,
                "num_ctx": 1024,
            }
            task_id = task_id or str(uuid.uuid4())
            task = LLMRequest(
                id=task_id,
                messages=messages,
                stream=stream,
                options=options,
            )
            self._active_tasks[task_id] = task
            self._queue.put(task)
            logger.info(f"Submitted task: {task_id}")
            return task_id

        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit("system", error_msg)
            return "error"

    def _process_item(self, task: LLMRequest):
        try:
            logger.info(f"LLM Processing task: {task['id']} - request {task}")
            response: ChatResponse = ollama.chat(
                model=self.model,
                messages=task["messages"],
                options=task["options"],
                stream=task["stream"],
                keep_alive=DEFAULT_KEEP_ALIVE,
                format=self.response_format,
            )
            task_id = task["id"]
            logger.info(f"LLM Generated response: {response}")

            if not task["stream"]:
                content = response["message"]["content"]

                self.generation_completed.emit(
                    LLMResponse(
                        task_id=task_id,
                        message=response["message"]["content"],
                        is_json=self.response_format is not None,
                    ),
                )
                del self._active_tasks[task_id]
                logger.info(f"Task {task_id} completed. Response: {content}")
                return

            llm_response = ""
            for chunk in response:
                if not self._running:
                    break

                if chunk.get("message", "") and chunk["message"].get(
                    "content", ""
                ):
                    content = chunk["message"]["content"]
                    llm_response += content
                    self.chunk_received.emit(task_id, content)

            if self._running:
                self.generation_completed.emit(
                    LLMResponse(
                        task_id=task_id,
                        message=llm_response,
                        is_json=self.response_format is not None,
                    )
                )
                del self._active_tasks[task_id]

        except Exception as e:
            logger.error(f"Error processing task: {str(e)}")
            self.error_occurred.emit(task["id"], str(e))
            if task["id"] in self._active_tasks:
                del self._active_tasks[task["id"]]
            raise e

    def cleanup(self):
        """Clean up resources"""
        try:
            # Cancel active tasks
            for task_id in list(self._active_tasks.keys()):
                self.error_occurred.emit(
                    task_id, "Service shutdown in progress"
                )
                del self._active_tasks[task_id]

            # Unload model
            ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": ""}],
                stream=False,
                keep_alive=0,
            )

            # Stop the service
            self.stop()
            logger.info("LLM Service cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            raise
