from decimal import Decimal

BASE = "/api/v1/admin-config"


def _post(client, headers, resource, payload):
    response = client.post(f"{BASE}/{resource}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_phase1_admin_requires_token(client):
    assert client.get(f"{BASE}/niches").status_code == 401
    assert client.post(f"{BASE}/niches", json={"name": "N", "slug": "n"}).status_code == 401


def test_phase1_full_configuration_gate_and_persistence(client, admin_headers, db):
    niche = _post(client, admin_headers, "niches", {"name": "Gate Niche", "slug": "gate-niche"})
    community = _post(
        client,
        admin_headers,
        "communities",
        {"niche_id": niche["id"], "name": "Gate Community", "slug": "gate-community"},
    )
    micros = [
        _post(
            client,
            admin_headers,
            "microniches",
            {
                "niche_id": niche["id"],
                "name": f"Content {index}",
                "slug": f"content-{index}",
                "sort_order": index,
            },
        )
        for index in range(1, 7)
    ]
    version = _post(
        client,
        admin_headers,
        "community-versions",
        {
            "community_id": community["id"],
            "version": 1,
            "name": "Gate V1",
            "promise_snapshot": {"benefits": "configured"},
            "microniche_ids": [item["id"] for item in micros],
        },
    )
    free = _post(
        client,
        admin_headers,
        "destinations",
        {
            "community_id": community["id"],
            "name": "Acquisition",
            "destination_type": "FREE_CHANNEL",
            "telegram_chat_id": "gate-free",
        },
    )
    vip = _post(
        client,
        admin_headers,
        "destinations",
        {
            "community_id": community["id"],
            "name": "Members Forum",
            "destination_type": "VIP_FORUM",
            "telegram_chat_id": "gate-vip",
        },
    )
    topics = [
        _post(
            client,
            admin_headers,
            "topics",
            {
                "destination_id": vip["id"],
                "name": "Geral/Avisos",
                "role": "GENERAL",
                "message_thread_id": 100,
            },
        ),
        _post(
            client,
            admin_headers,
            "topics",
            {
                "destination_id": vip["id"],
                "name": "Pedidos/Papo",
                "role": "REQUESTS",
                "message_thread_id": 101,
            },
        ),
    ]
    topics.extend(
        _post(
            client,
            admin_headers,
            "topics",
            {
                "destination_id": vip["id"],
                "microniche_id": micro["id"],
                "name": micro["name"],
                "role": "CONTENT",
                "message_thread_id": 101 + index,
            },
        )
        for index, micro in enumerate(micros, 1)
    )
    product = _post(
        client,
        admin_headers,
        "products",
        {"community_version_id": version["id"], "name": "Gate Product", "slug": "gate-product"},
    )
    plans = [
        _post(
            client,
            admin_headers,
            "price-plans",
            {"product_id": product["id"], "kind": "WEEKLY", "amount": "14.90", "duration_days": 7},
        ),
        _post(
            client,
            admin_headers,
            "price-plans",
            {
                "product_id": product["id"],
                "kind": "MONTHLY",
                "amount": "29.90",
                "duration_days": 30,
            },
        ),
        _post(
            client,
            admin_headers,
            "price-plans",
            {"product_id": product["id"], "kind": "LIFETIME", "amount": "37.90", "lifetime": True},
        ),
    ]
    offer = _post(
        client,
        admin_headers,
        "offers",
        {
            "name": "Launch Offer",
            "kind": "DISCOUNT",
            "config": {"percent": 10},
            "products": [{"product_id": product["id"], "role": "TARGET"}],
            "conditions": [{"condition_type": "NEW_CUSTOMER", "config": {}}],
        },
    )
    slot = _post(
        client,
        admin_headers,
        "copy-slots",
        {"key": "GATE_HERO", "description": "Gate hero context"},
    )
    variant = _post(
        client,
        admin_headers,
        "copy-variants",
        {
            "slot_id": slot["id"],
            "product_id": product["id"],
            "text": "Configurable copy",
            "weight": 25,
        },
    )

    assert free["destination_type"] == "FREE_CHANNEL"
    assert len(topics) == 8
    assert [Decimal(item["amount"]) for item in plans] == [
        Decimal("14.90"),
        Decimal("29.90"),
        Decimal("37.90"),
    ]
    assert offer["products"] == [
        {"offer_id": offer["id"], "product_id": product["id"], "role": "TARGET"}
    ]

    assert (
        client.patch(
            f"{BASE}/communities/{community['id']}",
            json={"name": "Gate Community Edited"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{BASE}/price-plans/{plans[0]['id']}", json={"active": False}, headers=admin_headers
        ).json()["active"]
        is False
    )
    assert (
        client.patch(
            f"{BASE}/copy-variants/{variant['id']}",
            json={"text": "Edited configurable copy"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    db.expire_all()
    assert (
        client.get(f"{BASE}/communities/{community['id']}", headers=admin_headers).json()["name"]
        == "Gate Community Edited"
    )
    reloaded_version = client.get(
        f"{BASE}/community-versions/{version['id']}", headers=admin_headers
    ).json()
    assert set(reloaded_version["microniche_ids"]) == {item["id"] for item in micros}
    assert (
        client.get(f"{BASE}/copy-variants/{variant['id']}", headers=admin_headers).json()["text"]
        == "Edited configurable copy"
    )

    assert (
        client.delete(f"{BASE}/copy-variants/{variant['id']}", headers=admin_headers).status_code
        == 204
    )
    assert (
        client.delete(f"{BASE}/copy-slots/{slot['id']}", headers=admin_headers).status_code == 204
    )
    assert client.delete(f"{BASE}/offers/{offer['id']}", headers=admin_headers).status_code == 204
    for plan in plans:
        assert (
            client.delete(f"{BASE}/price-plans/{plan['id']}", headers=admin_headers).status_code
            == 204
        )
    for topic in topics:
        assert (
            client.delete(f"{BASE}/topics/{topic['id']}", headers=admin_headers).status_code == 204
        )
    assert (
        client.delete(f"{BASE}/products/{product['id']}", headers=admin_headers).status_code == 204
    )
    assert (
        client.delete(f"{BASE}/destinations/{free['id']}", headers=admin_headers).status_code == 204
    )
    assert (
        client.delete(f"{BASE}/destinations/{vip['id']}", headers=admin_headers).status_code == 204
    )
    assert (
        client.delete(
            f"{BASE}/community-versions/{version['id']}", headers=admin_headers
        ).status_code
        == 204
    )
    for micro in micros:
        assert (
            client.delete(f"{BASE}/microniches/{micro['id']}", headers=admin_headers).status_code
            == 204
        )
    assert (
        client.delete(f"{BASE}/communities/{community['id']}", headers=admin_headers).status_code
        == 204
    )
    assert client.delete(f"{BASE}/niches/{niche['id']}", headers=admin_headers).status_code == 204


def test_phase1_validation_activation_and_safe_delete(client, admin_headers):
    niche = _post(client, admin_headers, "niches", {"name": "Delete Test", "slug": "delete-test"})
    micro = _post(
        client,
        admin_headers,
        "microniches",
        {"niche_id": niche["id"], "name": "Child", "slug": "child"},
    )
    blocked = client.delete(f"{BASE}/niches/{niche['id']}", headers=admin_headers)
    assert blocked.status_code == 409
    assert "microniches" in blocked.json()["detail"]
    assert (
        client.patch(
            f"{BASE}/microniches/{micro['id']}", json={"active": False}, headers=admin_headers
        ).json()["active"]
        is False
    )
    assert (
        client.delete(f"{BASE}/microniches/{micro['id']}", headers=admin_headers).status_code == 204
    )
    assert client.delete(f"{BASE}/niches/{niche['id']}", headers=admin_headers).status_code == 204
    assert (
        client.post(
            f"{BASE}/destinations",
            json={"name": "Bad", "destination_type": "INVALID", "telegram_chat_id": "bad"},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/price-plans",
            json={"product_id": "missing", "kind": "LIFETIME", "amount": "1.00", "lifetime": False},
            headers=admin_headers,
        ).status_code
        == 422
    )
