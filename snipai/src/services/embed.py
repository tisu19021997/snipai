import uuid
from enum import StrEnum
from pathlib import Path
from typing import List, Optional

import numpy as np
import ollama
from loguru import logger
from PyQt6.QtCore import pyqtSignal
from typing_extensions import TypedDict

from snipai.src.common.utils import download_ollama_model
from snipai.src.services.base import BaseService


class InputType(StrEnum):
    IMAGE = "image"
    TEXT = "text"


class EmbeddingRequest(TypedDict):
    id: str
    text: Optional[str] = None
    image: Optional[str | Path] = None
    retrieval: bool = False


class EmbeddingService(BaseService):
    embed_completed = pyqtSignal(str, str)  # task_id, string ndarray
    TEXT_MODEL = "mxbai-embed-large"

    def __init__(self):
        super().__init__()
        self._loaded_models: List[str] = []
        self._active_tasks = {}
        self._download_models()

        self.start()
        logger.info("Embedding Service initialized")

    def encode(
        self,
        text: Optional[str] = None,
        image: Optional[str | Path] = None,
        task_id: Optional[str] = None,
        retrieval: bool = False,
    ):
        task_id = task_id or str(uuid.uuid4())
        task = EmbeddingRequest(
            id=task_id, text=text, image=image, retrieval=retrieval
        )
        self._queue.put(task)
        logger.info(f"Submitted task: {task_id}")
        return task_id

    def _binary_quantize_embeddings(
        self, embeddings: np.ndarray | List
    ) -> np.ndarray:
        """Output dimension will be input dimension divide by 8"""
        if isinstance(embeddings, list):
            embeddings = np.array(embeddings)
        # from sentence_transformer.quantize_embeddings
        return (
            np.packbits(embeddings > 0).reshape(embeddings.shape[0], -1) - 128
        ).astype(np.int8)

    def _encode(
        self,
        text: Optional[str] = None,
        image: Optional[str | Path] = None,
        binary: bool = True,
        retrieval: bool = False,
    ):
        if text:
            base_prompt = (
                "Represent this sentence for searching relevant passages: "
            )
            prompt = f"{base_prompt}{text}" if retrieval else text
            response = ollama.embed(
                model=self.TEXT_MODEL,
                input=prompt,
                keep_alive=60 * 60,
            )
            self._loaded_models.append(self.TEXT_MODEL)
            embeddings = response["embeddings"]
            if binary:
                embeddings = self._binary_quantize_embeddings(embeddings)

            return embeddings

        if image:
            raise ValueError("Embedding images is not supported yet.")

        return embeddings

    def _process_item(self, request: EmbeddingRequest):
        try:
            if request["text"]:
                future_text = self.executor.submit(
                    self._encode,
                    text=request["text"],
                    binary=True,
                    retrieval=request["retrieval"],
                )
                embeddings = future_text.result()
                embeddings_str = np.array2string(np.array(embeddings))

                self.embed_completed.emit(request["id"], embeddings_str)
                logger.info(f"Task {request['id']} completed.")
            if request["image"]:
                # TODO: add image embedding
                raise ValueError("Embedding images is not supported yet.")

        except Exception as e:
            logger.error(f"Error processing task: {str(e)}")
            self.error_occurred.emit(str(e))

    def cleanup(self):
        try:
            for model in self._loaded_models:
                # Close the connection to the model
                ollama.embed(model=model, input=" ", keep_alive=0)
            self.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            raise

    def _download_models(self):
        for model in [self.TEXT_MODEL]:
            download_ollama_model(model)
