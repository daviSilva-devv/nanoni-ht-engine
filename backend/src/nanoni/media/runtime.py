from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

FOLDERS = ("inbox", "processing", "ready", "failed", "temp")
IMAGE_EXTENSIONS = {".avif", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def ensure_runtime_layout(root: Path) -> dict[str, Path]:
    resolved_root = root.resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)
    layout = {"root": resolved_root}
    for name in FOLDERS:
        folder = resolved_root / name
        folder.mkdir(parents=True, exist_ok=True)
        layout[name] = folder
    return layout


def ensure_within(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("path escapes media root")
    return resolved_path


def internal_filename(original_filename: str) -> str:
    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        extension = ""
    return f"{uuid4().hex}{extension}"


def media_type_for(path: Path) -> str:
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "IMAGE"
    if extension in VIDEO_EXTENSIONS:
        return "VIDEO"
    raise ValueError(f"unsupported media extension: {extension or '<none>'}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def move_without_overwrite(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    source.rename(destination)
    return destination


def promote_to_ready(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent.name == "ready":
        return resolved
    if resolved.parent.name != "processing":
        raise ValueError("only files in processing can be promoted to ready")
    root = resolved.parent.parent
    ensure_within(root, resolved)
    ready = ensure_runtime_layout(root)["ready"]
    destination = ready / resolved.name
    if destination.exists():
        if destination.samefile(resolved):
            return destination
        destination = ready / internal_filename(resolved.name)
    return move_without_overwrite(resolved, destination)


def original_file(path_value: str, root: Path) -> Path:
    path = ensure_within(root, Path(path_value))
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
