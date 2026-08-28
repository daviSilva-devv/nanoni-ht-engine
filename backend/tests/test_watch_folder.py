from nanoni.media.runtime import ensure_runtime_layout
from nanoni.media.watch_folder import import_inbox_once


def test_watch_folder_imports_supported_and_quarantines_unknown(db, tmp_path):
    layout = ensure_runtime_layout(tmp_path)
    (layout["inbox"] / "video.mp4").write_bytes(b"fake-video")
    (layout["inbox"] / "notes.exe").write_bytes(b"nope")
    ids = import_inbox_once(db, root=tmp_path)
    assert len(ids) == 1
    assert (layout["processing"] / "video.mp4").exists()
    assert (layout["failed"] / "notes.exe").exists()
