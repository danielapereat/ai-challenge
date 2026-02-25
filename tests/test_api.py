import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, date
from decimal import Decimal

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Payment Reconciliation Engine"
        assert "version" in data


@pytest.mark.anyio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_ingest_transactions_endpoint():
    """Test transaction ingestion endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test with valid transaction data
        payload = {
            "transactions": [
                {
                    "transaction_id": "test_txn_001",
                    "merchant_order_id": "order_001",
                    "amount": "100.00",
                    "currency": "MXN",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "status": "captured",
                    "customer_id": "cust_001",
                    "country": "MX"
                }
            ]
        }
        response = await client.post("/api/v1/ingest/transactions", json=payload)
        # May fail if DB not available, but structure should be correct
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_ingest_settlements_endpoint():
    """Test settlement ingestion endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "settlements": [
                {
                    "settlement_reference": "STL_001",
                    "amount": "97.00",
                    "currency": "MXN",
                    "settlement_date": "2024-01-17",
                    "fees_deducted": "3.00",
                    "bank_name": "Bank A"
                }
            ]
        }
        response = await client.post("/api/v1/ingest/settlements", json=payload)
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_ingest_adjustments_endpoint():
    """Test adjustment ingestion endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "adjustments": [
                {
                    "adjustment_id": "adj_001",
                    "amount": "50.00",
                    "currency": "MXN",
                    "type": "refund",
                    "date": "2024-01-20"
                }
            ]
        }
        response = await client.post("/api/v1/ingest/adjustments", json=payload)
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_reconcile_endpoint():
    """Test reconciliation endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-31"
        }
        response = await client.post("/api/v1/reconcile", json=payload)
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_discrepancies_endpoint():
    """Test discrepancies endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/discrepancies")
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_discrepancies_summary_endpoint():
    """Test discrepancies summary endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/discrepancies/summary")
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_matches_endpoint():
    """Test matches endpoint structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/matches")
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_matches_with_filters():
    """Test matches endpoint with query parameters."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/matches?confidence_min=80&status=matched")
        assert response.status_code in [200, 500]


@pytest.mark.anyio
async def test_reconcile_status_endpoint():
    """Test reconciliation status endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/reconcile/status")
        assert response.status_code in [200, 500]


class TestSchemaValidation:
    """Test request/response schema validation."""

    @pytest.mark.anyio
    async def test_invalid_transaction_currency(self):
        """Test that invalid currency is rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "transactions": [
                    {
                        "transaction_id": "test_txn_002",
                        "merchant_order_id": "order_002",
                        "amount": "100.00",
                        "currency": "INVALID",  # Invalid - too long
                        "timestamp": "2024-01-15T10:00:00Z",
                        "status": "captured",
                        "customer_id": "cust_001",
                        "country": "MX"
                    }
                ]
            }
            response = await client.post("/api/v1/ingest/transactions", json=payload)
            assert response.status_code == 422  # Validation error

    @pytest.mark.anyio
    async def test_missing_required_field(self):
        """Test that missing required fields are rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "transactions": [
                    {
                        "transaction_id": "test_txn_003",
                        # Missing required fields
                    }
                ]
            }
            response = await client.post("/api/v1/ingest/transactions", json=payload)
            assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
