from pathlib import Path


def get_project_root() -> Path:
    """Returns project root folder."""
    return Path(__file__).parent.parent.parent


class ProjectPaths:
    """Project paths manager."""

    def __init__(self):
        self.ROOT = get_project_root()
        self.SRC = self.ROOT / "src"
        self.ASSET = self.ROOT / "assets"
        self.IMG = self.ASSET / "images"
        self.CONFIG = self.ASSET / "configs"
        self.LOGO = self.ASSET / "icons"
        self.QSS = self.ASSET / "qss"

    def ensure_dir(self, path: Path) -> Path:
        """Create directory if it doesn't exist."""
        path.mkdir(parents=True, exist_ok=True)
        return path


# Single instance to be used across project
paths = ProjectPaths()
