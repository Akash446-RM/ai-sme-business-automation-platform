"""Authentication endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_first_registered_account_becomes_owner(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "first@smedemo.com",
            "full_name": "First User",
            "password": "Password123",
            "role": "staff",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "owner"
    assert body["is_active"] is True
    assert "hashed_password" not in body


def test_second_account_keeps_requested_role(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@smedemo.com",
            "full_name": "Owner",
            "password": "Password123",
        },
    )
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "staff@smedemo.com",
            "full_name": "Staff Member",
            "password": "Password123",
            "role": "staff",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "staff"


def test_duplicate_email_returns_conflict(client: TestClient) -> None:
    payload = {
        "email": "dup@smedemo.com",
        "full_name": "Duplicate",
        "password": "Password123",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "password",
    ["short1", "nodigitspassword", "12345678"],
)
def test_weak_passwords_rejected(client: TestClient, password: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@smedemo.com", "full_name": "Weak", "password": password},
    )
    assert response.status_code == 422


def test_login_returns_token_and_user(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@smedemo.com", "full_name": "Login", "password": "Password123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@smedemo.com", "password": "Password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "login@smedemo.com"


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrong@smedemo.com", "full_name": "Wrong", "password": "Password123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@smedemo.com", "password": "WrongPass123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_login_with_unknown_email_fails(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@smedemo.com", "password": "Password123"},
    )
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "owner@smedemo.com"


def test_invalid_token_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_role_gate_blocks_staff_from_owner_endpoint(
    client: TestClient, auth_headers: dict
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "s@smedemo.com", "full_name": "Staff", "password": "Password123"},
    )
    staff_token = client.post(
        "/api/v1/auth/login", json={"email": "s@smedemo.com", "password": "Password123"}
    ).json()["access_token"]

    response = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"email": "x@smedemo.com", "full_name": "X", "password": "Password123"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_authorized"


def test_change_password_flow(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={"current_password": "OwnerPass123", "new_password": "BrandNew456"},
    )
    assert response.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@smedemo.com", "password": "OwnerPass123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@smedemo.com", "password": "BrandNew456"},
        ).status_code
        == 200
    )


def test_owner_cannot_deactivate_self(client: TestClient, auth_headers: dict) -> None:
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    response = client.delete(f"/api/v1/auth/users/{me['id']}", headers=auth_headers)
    assert response.status_code == 422
