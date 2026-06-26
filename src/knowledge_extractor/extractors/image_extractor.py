import shutil
from pathlib import Path


def extract_image(file_path: Path, temp_dir: Path) -> str:
    img_dir = temp_dir / "standalone_images"
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / file_path.name
    shutil.copy2(file_path, dest)
    return f"![image]({dest})\n"
