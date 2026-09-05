import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from nanoni.domain.models import ContentCandidate, ContentPack, PackItem, Source
from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.domain.services.content import import_manifest_with_classification

POSTGRES_TEST_URL = os.getenv("NANONI_TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="NANONI_TEST_POSTGRES_URL is required for the PostgreSQL integration gate",
)
def test_phase2a_persists_candidate_pack_and_items_on_postgresql():
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    assert engine.dialect.name == "postgresql"

    with Session(engine, expire_on_commit=False) as db:
        transaction = db.begin()
        try:
            external_id = f"phase2a-test-{uuid4().hex}"
            source = Source(name=external_id, adapter="manual")
            db.add(source)
            db.flush()
            outcome = import_manifest_with_classification(
                db,
                source_id=source.id,
                manifest=MediaManifest(
                    source="manual",
                    source_external_id=external_id,
                    media=[
                        ManifestAsset(
                            external_item_id=f"{external_id}-item",
                            media_type="IMAGE",
                            sha256="f" * 64,
                        )
                    ],
                ),
            )
            db.flush()
            db.expire_all()

            candidate = db.get(ContentCandidate, outcome.candidate.id)
            pack = db.scalar(
                select(ContentPack).where(ContentPack.candidate_id == outcome.candidate.id)
            )
            assert candidate is not None
            assert pack is not None
            assert db.scalar(select(PackItem).where(PackItem.pack_id == pack.id)) is not None
        finally:
            transaction.rollback()
            engine.dispose()
