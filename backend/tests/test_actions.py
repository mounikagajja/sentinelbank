from backend.app.models import Account


def test_freeze_account(client, seeded):
    account_id = seeded["account"].id
    response = client.patch(
        f"/api/v1/accounts/{account_id}/status",
        json={"status": "frozen", "reason": "Suspected card compromise"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "frozen"


def test_freeze_then_unfreeze(client, seeded):
    account_id = seeded["account"].id
    client.patch(
        f"/api/v1/accounts/{account_id}/status",
        json={"status": "frozen", "reason": "Suspected card compromise"},
    )
    response = client.patch(
        f"/api/v1/accounts/{account_id}/status",
        json={"status": "active", "reason": "Customer confirmed the charges"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_freezing_a_frozen_account_conflicts(client, seeded):
    account_id = seeded["account"].id
    body = {"status": "frozen", "reason": "Suspected card compromise"}
    client.patch(f"/api/v1/accounts/{account_id}/status", json=body)
    response = client.patch(f"/api/v1/accounts/{account_id}/status", json=body)
    assert response.status_code == 409


def test_reason_is_required(client, seeded):
    response = client.patch(
        f"/api/v1/accounts/{seeded['account'].id}/status", json={"status": "frozen"}
    )
    assert response.status_code == 422


def test_unknown_account_status_is_rejected(client, seeded):
    response = client.patch(
        f"/api/v1/accounts/{seeded['account'].id}/status",
        json={"status": "closed", "reason": "Customer request"},
    )
    assert response.status_code == 422


def test_confirm_flag_sets_reviewed_at(client, seeded):
    response = client.patch(
        f"/api/v1/flags/{seeded['flag'].id}/status",
        json={"status": "confirmed", "note": "Customer did not make this purchase"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["reviewed_at"] is not None


def test_dismiss_flag(client, seeded):
    response = client.patch(
        f"/api/v1/flags/{seeded['flag'].id}/status", json={"status": "dismissed"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


def test_reviewing_a_reviewed_flag_conflicts(client, seeded):
    flag_id = seeded["flag"].id
    client.patch(f"/api/v1/flags/{flag_id}/status", json={"status": "confirmed"})
    response = client.patch(f"/api/v1/flags/{flag_id}/status", json={"status": "dismissed"})
    assert response.status_code == 409


def test_open_is_not_a_valid_review_outcome(client, seeded):
    response = client.patch(f"/api/v1/flags/{seeded['flag'].id}/status", json={"status": "open"})
    assert response.status_code == 422


def test_frozen_account_is_visible_through_the_read_endpoint(client, db, seeded):
    account_id = seeded["account"].id
    client.patch(
        f"/api/v1/accounts/{account_id}/status",
        json={"status": "frozen", "reason": "Suspected card compromise"},
    )
    assert client.get(f"/api/v1/accounts/{account_id}").json()["status"] == "frozen"
    assert db.get(Account, account_id).status == "frozen"
