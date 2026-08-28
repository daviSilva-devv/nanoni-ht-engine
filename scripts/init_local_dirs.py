import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("NANONI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
media = PROJECT_ROOT / "runtime" / "media"
for name in ("inbox", "processing", "published", "failed", "temp"):
    path = media / name
    path.mkdir(parents=True, exist_ok=True)
    print(path)
