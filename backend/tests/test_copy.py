import random

from nanoni.domain.models import CopySlot, CopyVariant
from nanoni.domain.services.copy_engine import choose_copy


def test_copy_is_configurable_and_weighted(db):
    slot = CopySlot(key="BOT_HERO")
    db.add(slot)
    db.flush()
    db.add_all(
        [
            CopyVariant(slot_id=slot.id, text="A", weight=1),
            CopyVariant(slot_id=slot.id, text="B", weight=100),
        ]
    )
    db.flush()
    selected = [choose_copy(db, "BOT_HERO", rng=random.Random(seed)).text for seed in range(30)]
    assert selected.count("B") > selected.count("A")
