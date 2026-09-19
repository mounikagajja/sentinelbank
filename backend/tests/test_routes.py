def test_get_customer_returns_the_customer(client, seeded):
    customer = seeded["customer"]
    response = client.get(f"/api/v1/customers/{customer.id}")
    assert response.status_code == 200
    assert response.json()["email"] == "api@example.com"


def test_get_customer_404_when_missing(client):
    assert client.get("/api/v1/customers/99999999").status_code == 404


def test_list_customer_accounts(client, seeded):
    response = client.get(f"/api/v1/customers/{seeded['customer'].id}/accounts")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["account_type"] == "checking"


def test_account_transactions_are_newest_first(client, seeded):
    response = client.get(f"/api/v1/accounts/{seeded['account'].id}/transactions")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    times = [item["occurred_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)


def test_account_transactions_pagination(client, seeded):
    account_id = seeded["account"].id
    first = client.get(f"/api/v1/accounts/{account_id}/transactions?limit=2&offset=0").json()
    second = client.get(f"/api/v1/accounts/{account_id}/transactions?limit=2&offset=2").json()
    assert first["total"] == second["total"] == 5
    assert len(first["items"]) == len(second["items"]) == 2
    assert {item["id"] for item in first["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )


def test_limit_above_maximum_is_rejected(client, seeded):
    response = client.get(f"/api/v1/accounts/{seeded['account'].id}/transactions?limit=500")
    assert response.status_code == 422


def test_account_transactions_404_when_account_missing(client):
    assert client.get("/api/v1/accounts/99999999/transactions").status_code == 404


def test_amount_keeps_two_decimal_places(client, seeded):
    transaction = seeded["transactions"][0]
    response = client.get(f"/api/v1/transactions/{transaction.id}")
    assert response.status_code == 200
    assert response.json()["amount"] == "25.00"


def test_list_flags_includes_the_joined_transaction(client, seeded):
    response = client.get("/api/v1/flags")
    assert response.status_code == 200
    body = response.json()
    ids = [item["flag"]["id"] for item in body["items"]]
    assert seeded["flag"].id in ids
    matching = next(item for item in body["items"] if item["flag"]["id"] == seeded["flag"].id)
    assert matching["transaction"]["id"] == seeded["transactions"][4].id
    assert matching["transaction"]["merchant_name"] == "Safeway"


def test_flags_min_score_filter_excludes_lower_scores(client, seeded):
    high = client.get("/api/v1/flags?min_score=0.95").json()
    assert seeded["flag"].id not in [item["flag"]["id"] for item in high["items"]]


def test_flags_rejects_unknown_status(client):
    response = client.get("/api/v1/flags?status=banana")
    assert response.status_code == 422


def test_get_flag_by_id(client, seeded):
    response = client.get(f"/api/v1/flags/{seeded['flag'].id}")
    assert response.status_code == 200
    assert response.json()["flag"]["model_version"] == "xgb-test"


def test_get_flag_404_when_missing(client):
    assert client.get("/api/v1/flags/99999999").status_code == 404
