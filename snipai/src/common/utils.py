import re

import ollama
from PyQt6.QtCore import QLineF, QPointF
from tqdm import tqdm


def slugify(text: str, separator: str = "_") -> str:
    """
    A function that takes a text and formats it into a slug by replacing special characters, trimming whitespace, and replacing spaces with a specified separator.

    Parameters:
        text (str): The text to be slugified.
        separator (str, optional): The separator used to replace spaces in the slug. Defaults to "_".

    Returns:
        str: The slugified text.
    """
    text = re.sub(r"[^\w]", " ", text.strip().lower())
    return re.sub(r"\s+", separator, text.strip())


def euclidean_distance_qline(point1: QPointF, point2: QPointF) -> float:
    """Calculates Euclidean distance using QLineF"""
    line = QLineF(point1, point2)
    return line.length()


def download_ollama_model(model_name: str):
    """
    Downloads an Ollama model from the specified URL and saves it to a local file.
    """
    downloaded_models = ollama.list().models
    has_downloaded = any(
        model_name in model.model for model in downloaded_models
    )
    if not has_downloaded:
        with tqdm(
            desc=f"Downloading {model_name}", unit="B", unit_scale=True
        ) as pbar:
            last_completed = 0
            for p in ollama.pull(model_name, stream=True):
                completed = p.get("completed")
                total = p.get("total")
                if completed is not None and total is not None:
                    delta = completed - last_completed
                    pbar.total = total
                    pbar.update(delta)
                    last_completed = completed

                if p.get("status"):
                    msg = f"Downloading {model_name} - {p['status']}"
                    pbar.set_description(msg)
