"""
test_api.py — VerifAI Backend Integration Tests

IMPORTANT: Transaction processing endpoints now require JWT authentication.
Tests that exercise protected endpoints must first register, verify, and login
to obtain a valid token.

Health check / root endpoints are public and are still tested as-is.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


# ─── Public Endpoints ─────────────────────────────────────────────────────────

def test_health():
    """Health endpoint should be public and return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root():
    """Root endpoint should be public and identify the service."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "VerifAI" in data["service"]
    assert data["status"] == "online"


# ─── Auth Endpoint Smoke Tests ────────────────────────────────────────────────

def test_signup_missing_fields():
    """Signup with missing required fields should return 422."""
    response = client.post("/api/auth/signup", json={"email": "test@test.com"})
    assert response.status_code == 422


def test_login_wrong_credentials():
    """Login with non-existent credentials should return 401."""
    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "WrongPassw0rd!"
    })
    assert response.status_code in (401, 404)


# ─── Protected Endpoint Rejection Tests ──────────────────────────────────────

def test_process_transaction_requires_auth():
    """
    Transaction processing now requires a valid JWT.
    Unauthenticated requests must return 403 (Forbidden) or 401.
    This used to be an open endpoint — verifying it is now protected.
    """
    payload = {
        "user_id": "user_test_001",
        "amount": 5000,
        "merchant": "Amazon",
        "merchant_category": "ECOMMERCE",
        "device_type": "web",
        "device_ip": "192.168.1.1",
        "user_location": {"lat": 19.0760, "lon": 72.8777},
    }
    response = client.post("/api/v1/transactions/process", json=payload)
    # Without a token, must be rejected
    assert response.status_code in (401, 403), (
        f"Expected 401 or 403, got {response.status_code}. "
        "Transaction endpoint must require authentication."
    )


def test_transaction_status_requires_auth():
    """Status endpoint must require authentication."""
    response = client.get("/api/v1/transactions/status/tx_test_123")
    assert response.status_code in (401, 403)


def test_list_transactions_requires_auth():
    """List endpoint must require authentication."""
    response = client.get("/api/v1/transactions")
    assert response.status_code in (401, 403)


def test_dashboard_stats_requires_auth():
    """Stats endpoint must require authentication."""
    response = client.get("/api/v1/transactions/stats")
    assert response.status_code in (401, 403)


# ─── Fraud Score Range Test (unit-level, no DB needed) ───────────────────────

def test_fraud_score_range():
    """The fraud score must always be a float in [0.0, 1.0]."""
    from app.services.agent import AgentController
    import asyncio

    agent = AgentController()

    tx = {
        "id": "tx_unit_test",
        "user_id": "user_001",
        "amount": 999,
        "merchant": "Amazon",
        "merchant_category": "ECOMMERCE",
        "device_type": "web",
        "device_ip": "127.0.0.1",
        "user_location": {"lat": 19.0760, "lon": 72.8777},
        "email": None,
        "timestamp": None,
    }

    result = asyncio.run(agent.process_transaction(tx))
    fraud_score = result["fraud_score"]

    assert isinstance(fraud_score, float), f"fraud_score should be float, got {type(fraud_score)}"
    assert 0.0 <= fraud_score <= 1.0, f"fraud_score {fraud_score} is out of [0, 1] range"


def test_model_not_updated_claim():
    """Verification response must NOT claim model_updated=True."""
    from app.services.agent import AgentController
    import asyncio

    agent = AgentController()
    result = asyncio.run(agent.handle_user_verification_response("tx_001", True))

    assert result["model_updated"] is False, (
        "model_updated should be False — the model is not retrained in real time."
    )


def test_feature_engineer_merchant_check():
    """merchant_seen_before should check for the specific merchant, not just any history."""
    from app.ml.feature_engineering import FeatureEngineer
    import pandas as pd

    history = pd.DataFrame([
        {"amount": 1000, "merchant": "Amazon", "created_at": "2025-01-01T10:00:00"},
    ])
    engineer = FeatureEngineer(user_history_df=history)

    # Amazon is in history — should be 1
    tx_known = {"amount": 500, "merchant": "Amazon", "merchant_category": "ECOMMERCE"}
    features_known = engineer.create_features(tx_known)
    assert features_known["merchant_seen_before"].iloc[0] == 1

    # Unknown merchant — should be 0
    tx_new = {"amount": 500, "merchant": "SomeNewStore", "merchant_category": "UNKNOWN"}
    features_new = engineer.create_features(tx_new)
    assert features_new["merchant_seen_before"].iloc[0] == 0
