from nanoni.core.config import get_settings


def test_telegram_webhook_requires_configured_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")

    response = client.post("/api/v1/telegram/webhook", json={"update_id": 1})

    assert response.status_code == 401


def test_telegram_webhook_ignores_unrelated_authenticated_update(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        json={"update_id": 2},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "handled": False}
