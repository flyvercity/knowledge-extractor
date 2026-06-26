import shutil
from pathlib import Path
from .utils import get_img_dir


def extract_image(file_path: Path, temp_dir: Path) -> str:
    img_dir = get_img_dir(temp_dir, file_path)
    dest = img_dir / file_path.name
    shutil.copy2(file_path, dest)
    return f"![image]({dest.resolve()})\n"
