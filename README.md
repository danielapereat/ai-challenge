# Payment Reconciliation Engine

A backend service that matches payment transactions across three data sources (Yuno transactions, bank settlements, refunds/chargebacks), identifies discrepancies, and exposes results through a REST API.

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (async support, auto-generated OpenAPI docs)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy + asyncpg (async support)
- **Data Generation**: Faker

## Quick Start

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

### 4. Generate and Seed Test Data

```bash
python scripts/generate_test_data.py
python scripts/seed_database.py
```

### 5. Run Reconciliation

```bash
# Trigger reconciliation
curl -X POST http://localhost:8000/api/v1/reconcile

# Check discrepancies
curl http://localhost:8000/api/v1/discrepancies | jq

# Check matches
curl "http://localhost:8000/api/v1/matches?confidence_min=80" | jq

# View summary
curl http://localhost:8000/api/v1/discrepancies/summary | jq
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Data Ingestion

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ingest/transactions` | POST | Ingest transactions |
| `/api/v1/ingest/settlements` | POST | Ingest settlements |
| `/api/v1/ingest/adjustments` | POST | Ingest adjustments |
| `/api/v1/ingest/file` | POST | Ingest from JSON file |

### Reconciliation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/reconcile` | POST | Run reconciliation process |
| `/api/v1/reconcile/status` | GET | Get reconciliation status |

### Discrepancies

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/discrepancies` | GET | Get discrepancies with filtering |
| `/api/v1/discrepancies/summary` | GET | Get summary statistics |

### Matches

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/matches` | GET | Get match results |
| `/api/v1/matches/{transaction_id}` | GET | Get match for specific transaction |

## Data Models

### Transaction
- `transaction_id`: Yuno transaction ID
- `merchant_order_id`: Merchant's order reference
- `amount`: Transaction amount
- `currency`: ISO currency code (MXN, COP, BRL)
- `timestamp`: Transaction timestamp
- `status`: authorized | captured | failed
- `customer_id`: Customer identifier
- `country`: MX, CO, BR

### Settlement
- `settlement_reference`: Bank reference
- `amount`: Settled amount (after fees)
- `gross_amount`: Original amount before fees
- `currency`: Settlement currency
- `settlement_date`: When money arrived
- `transaction_reference`: Reference to original transaction
- `fees_deducted`: Fee amount
- `bank_name`: Originating bank

### Adjustment
- `adjustment_id`: Unique adjustment ID
- `transaction_reference`: Reference to original transaction
- `amount`: Adjustment amount
- `currency`: Currency
- `type`: refund | chargeback
- `date`: Adjustment date
- `reason_code`: Reason code

## Matching Engine

The matching engine uses a multi-phase approach:

### Phase 1: Exact ID Match (100% confidence)
Matches settlements to transactions by exact transaction ID.

### Phase 2: Amount + Date Match (80-95% confidence)
- Amount tolerance: 5% (to account for fees)
- Date window: 72 hours

### Phase 3: Fuzzy Match (70-85% confidence)
- Partial ID matching (first 8 characters)
- Merchant order ID matching

### Phase 4: Cross-Currency Match (60-80% confidence)
- Matches across different currencies with FX tolerance
- Flagged for review

### Phase 5: Adjustment Match
- Matches refunds and chargebacks to transactions
- Uses longer windows (30 days for refunds, 90 days for chargebacks)

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection URL |
| `AMOUNT_TOLERANCE_PERCENT` | `5.0` | Amount variance tolerance |
| `SETTLEMENT_WINDOW_HOURS` | `72` | Settlement date window |
| `MIN_CONFIDENCE_FOR_AUTO_MATCH` | `80` | Auto-match threshold |

## Project Structure

```
ai-challenge/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/routes/          # API endpoints
│   ├── services/            # Business logic
│   └── utils/               # Utility functions
├── scripts/
│   ├── generate_test_data.py
│   └── seed_database.py
├── tests/
├── data/                    # Generated test data
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Expected Test Results

With the generated test data:
- ~165 high-confidence matches (80%+)
- ~10-15 unmatched transactions
- ~5-8 unmatched settlements
- ~3 unmatched adjustments
- Discrepancies categorized by type and priority
