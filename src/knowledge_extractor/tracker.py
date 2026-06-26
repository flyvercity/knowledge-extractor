import json
from pathlib import Path
from .discovery import DiscoveredFile


class ProgressTracker:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def _key(self, file: DiscoveredFile) -> str:
        return str(file.relative_path)

    def is_processed(self, file: DiscoveredFile) -> bool:
        key = self._key(file)
        if key not in self.data:
            return False
        mtime = file.path.stat().st_mtime
        return self.data[key].get("mtime") == mtime

    def mark_processed(self, file: DiscoveredFile, output_path: Path):
        self.data[self._key(file)] = {
            "mtime": file.path.stat().st_mtime,
            "output": str(output_path),
        }
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get_pending(self, files: list[DiscoveredFile]) -> list[DiscoveredFile]:
        return [f for f in files if not self.is_processed(f)]
