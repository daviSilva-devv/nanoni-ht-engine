from pathlib import Path

from sqlalchemy import func, select

from nanoni.domain.models import ContentCandidate, ContentPack, MediaAsset, PackItem
from nanoni.media.runtime import ensure_runtime_layout
from nanoni.media.watch_folder import import_inbox_once, scan_watch_folder, watch_folder_status


def test_watch_folder_imports_supported_and_quarantines_unknown(db, tmp_path):
    layout = ensure_runtime_layout(tmp_path)
    (layout["inbox"] / "video.mp4").write_bytes(b"fake-video")
    (layout["inbox"] / "notes.exe").write_bytes(b"nope")

    result = scan_watch_folder(db, root=tmp_path)

    assert len(result.candidate_ids) == 1
    assert result.failed_files == ["notes.exe"]
    assert db.scalar(select(func.count(ContentCandidate.id))) == 1
    assert db.scalar(select(func.count(ContentPack.id))) == 1
    assert db.scalar(select(func.count(PackItem.id))) == 1
    assert len(list(layout["processing"].iterdir())) == 1
    assert len(list(layout["failed"].iterdir())) == 1
    folders, counts = watch_folder_status(tmp_path)
    assert set(folders) == {"inbox", "processing", "ready", "failed", "temp"}
    assert "published" not in folders
    assert counts["processing"] == 1
    assert counts["failed"] == 1


def test_watch_folder_recovers_untracked_processing_file_after_restart(db, tmp_path):
    layout = ensure_runtime_layout(tmp_path)
    orphan = layout["processing"] / "orphan.jpg"
    orphan.write_bytes(b"recover-me")

    result = scan_watch_folder(db, root=tmp_path)
    retried_ids = import_inbox_once(db, root=tmp_path)

    assert len(result.candidate_ids) == 1
    assert result.recovered_files == ["orphan.jpg"]
    assert retried_ids == []
    asset = db.scalar(select(MediaAsset))
    assert asset is not None
    assert Path(asset.local_path) == orphan.resolve()


def test_watch_folder_same_sha_reuses_one_physical_blob(db, tmp_path):
    layout = ensure_runtime_layout(tmp_path)
    (layout["inbox"] / "one.jpg").write_bytes(b"same")
    first = scan_watch_folder(db, root=tmp_path)
    (layout["inbox"] / "two.jpg").write_bytes(b"same")
    second = scan_watch_folder(db, root=tmp_path)

    assert len(first.candidate_ids) == len(second.candidate_ids) == 1
    assert db.scalar(select(func.count(MediaAsset.id))) == 1
    assert db.scalar(select(func.count(PackItem.id))) == 2
    assert len(list(layout["processing"].iterdir())) == 1
