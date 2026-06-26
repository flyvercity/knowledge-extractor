import hashlib
from pathlib import Path


def get_img_dir(temp_dir: Path, file_path: Path) -> Path:
    """Create a safe, unique image directory for a source file."""
    # Use a short hash + truncated stem to avoid path issues
    h = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    safe_name = file_path.stem[:40].replace(" ", "_") + f"_{h}"
    img_dir = temp_dir / "images" / safe_name
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir
