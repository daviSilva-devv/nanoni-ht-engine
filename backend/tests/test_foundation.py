from pathlib import Path

import pytest
from sqlalchemy import create_engine

from nanoni.core.config import Settings
from nanoni.scripts import seed_demo


def test_project_paths_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    settings = Settings(_env_file=None, project_root=project_root)

    assert settings.project_root == project_root.resolve()
    assert settings.media_root == (project_root / "runtime" / "media").resolve()
    assert settings.database_url == f"sqlite:///{(project_root / 'nanoni.db').as_posix()}"


def test_absolute_media_path_is_preserved(tmp_path):
    media_root = (tmp_path / "external-media").resolve()

    settings = Settings(_env_file=None, project_root=tmp_path, media_root=media_root)

    assert settings.media_root == media_root


def test_seed_fails_clearly_when_migrations_were_not_run(tmp_path, monkeypatch):
    empty_engine = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    monkeypatch.setattr(seed_demo, "engine", empty_engine)

    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        seed_demo.run()


def test_repository_env_file_is_absolute():
    env_file = Settings.model_config["env_file"]

    assert Path(env_file).is_absolute()
