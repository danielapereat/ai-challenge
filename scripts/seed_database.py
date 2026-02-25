#!/usr/bin/env python3
"""
Database seeding script for the reconciliation system.

Reads generated JSON files from data/ directory and inserts records
into the PostgreSQL database using the IngestionService.

Usage:
    python -m scripts.seed_database
    # or
    python scripts/seed_database.py
"""

import asyncio
import json
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

# Add the project root to the path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.services.ingestion import IngestionService
from app.schemas.transaction import TransactionCreate
from app.schemas.settlement import SettlementCreate
from app.schemas.adjustment import AdjustmentCreate


# Database configuration
DATABASE_URL = "postgresql+asyncpg://reconciliation:reconciliation@localhost:5432/reconciliation"

# Data file paths
DATA_DIR = project_root / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
SETTLEMENTS_FILE = DATA_DIR / "settlements.json"
ADJUSTMENTS_FILE = DATA_DIR / "adjustments.json"


def load_json_file(file_path: Path) -> list[dict]:
    """Load JSON data from a file."""
    if not file_path.exists():
        print(f"Warning: File not found: {file_path}")
        return []

    with open(file_path, "r") as f:
        data = json.load(f)

    # Handle both list format and dict with key format
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Try common keys
        for key in ["transactions", "settlements", "adjustments", "data"]:
            if key in data:
                return data[key]
        # Return empty if no known key found
        return []

    return []


def parse_transactions(data: list[dict]) -> list[TransactionCreate]:
    """Parse transaction data into TransactionCreate schemas."""
    transactions = []
    for item in data:
        try:
            # Parse timestamp - use created_at from JSON
            timestamp = item.get("timestamp") or item.get("created_at")
            if isinstance(timestamp, str):
                # Try ISO format first
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

            # Map fields from generated JSON to schema
            # JSON: merchant_reference -> Schema: merchant_order_id
            # JSON: created_at -> Schema: timestamp
            # JSON: customer_email -> Schema: customer_id
            # JSON: metadata.country -> Schema: country
            merchant_order_id = item.get("merchant_order_id") or item.get("merchant_reference", "")
            customer_id = item.get("customer_id") or item.get("customer_email", "")
            country = item.get("country") or (item.get("metadata", {}).get("country", "XX") if isinstance(item.get("metadata"), dict) else "XX")

            txn = TransactionCreate(
                transaction_id=item["transaction_id"],
                merchant_order_id=merchant_order_id,
                amount=Decimal(str(item["amount"])),
                currency=item["currency"],
                timestamp=timestamp,
                status=item["status"],
                customer_id=customer_id,
                country=country,
            )
            transactions.append(txn)
        except Exception as e:
            print(f"Error parsing transaction {item.get('transaction_id', 'unknown')}: {e}")

    return transactions


def parse_settlements(data: list[dict]) -> list[SettlementCreate]:
    """Parse settlement data into SettlementCreate schemas."""
    settlements = []
    for item in data:
        try:
            # Parse settlement_date - handle both date and datetime formats
            settlement_date = item.get("settlement_date")
            if isinstance(settlement_date, str):
                # Handle datetime string with time component
                if "T" in settlement_date:
                    settlement_date = datetime.fromisoformat(settlement_date.replace("Z", "+00:00")).date()
                else:
                    settlement_date = date.fromisoformat(settlement_date)

            # Map fields from generated JSON to schema
            # JSON: settlement_id -> Schema: settlement_reference
            # JSON: provider -> Schema: bank_name
            # JSON: original_amount -> Schema: gross_amount
            # JSON: fee_applied -> Schema: fees_deducted (converted to actual amount)
            settlement_reference = item.get("settlement_reference") or item.get("settlement_id")
            bank_name = item.get("bank_name") or item.get("provider", "unknown")
            gross_amount = item.get("gross_amount") or item.get("original_amount")

            # Calculate fees_deducted from fee_applied percentage if available
            amount = Decimal(str(item["amount"]))
            fee_applied = item.get("fee_applied")
            if fee_applied:
                # fee_applied is a percentage, calculate the actual fee amount
                fees_deducted = amount * Decimal(str(fee_applied)) / Decimal("100")
            else:
                fees_deducted = Decimal(str(item.get("fees_deducted", "0")))

            stl = SettlementCreate(
                settlement_reference=settlement_reference,
                amount=amount,
                gross_amount=Decimal(str(gross_amount)) if gross_amount else None,
                currency=item["currency"],
                settlement_date=settlement_date,
                transaction_reference=item.get("transaction_reference"),
                fees_deducted=fees_deducted,
                bank_name=bank_name,
            )
            settlements.append(stl)
        except Exception as e:
            print(f"Error parsing settlement {item.get('settlement_reference') or item.get('settlement_id', 'unknown')}: {e}")

    return settlements


def parse_adjustments(data: list[dict]) -> list[AdjustmentCreate]:
    """Parse adjustment data into AdjustmentCreate schemas."""
    adjustments = []
    for item in data:
        try:
            # Parse date - use adjustment_date from JSON or date
            adj_date = item.get("date") or item.get("adjustment_date")
            if isinstance(adj_date, str):
                # Handle both date and datetime formats
                if "T" in adj_date:
                    adj_date = datetime.fromisoformat(adj_date.replace("Z", "+00:00")).date()
                else:
                    adj_date = date.fromisoformat(adj_date)

            # Map fields from generated JSON to schema
            # JSON: transaction_id -> Schema: transaction_reference
            # JSON: adjustment_amount -> Schema: amount
            # JSON: adjustment_date -> Schema: date
            # JSON: reason -> Schema: reason_code
            transaction_reference = item.get("transaction_reference") or item.get("transaction_id")
            amount = item.get("amount") or item.get("adjustment_amount")
            reason_code = item.get("reason_code") or item.get("reason")

            adj = AdjustmentCreate(
                adjustment_id=item["adjustment_id"],
                transaction_reference=transaction_reference,
                amount=Decimal(str(amount)),
                currency=item["currency"],
                type=item["type"],
                date=adj_date,
                reason_code=reason_code,
            )
            adjustments.append(adj)
        except Exception as e:
            print(f"Error parsing adjustment {item.get('adjustment_id', 'unknown')}: {e}")

    return adjustments


async def seed_database():
    """Main function to seed the database with data from JSON files."""
    print("=" * 60)
    print("Database Seeding Script")
    print("=" * 60)
    print()

    # Create async engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Initialize database tables
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ready.")
    print()

    # Load JSON data
    print("Loading JSON data files...")
    print(f"  - Transactions: {TRANSACTIONS_FILE}")
    print(f"  - Settlements: {SETTLEMENTS_FILE}")
    print(f"  - Adjustments: {ADJUSTMENTS_FILE}")
    print()

    transactions_data = load_json_file(TRANSACTIONS_FILE)
    settlements_data = load_json_file(SETTLEMENTS_FILE)
    adjustments_data = load_json_file(ADJUSTMENTS_FILE)

    print(f"Loaded from JSON files:")
    print(f"  - Transactions: {len(transactions_data)} records")
    print(f"  - Settlements: {len(settlements_data)} records")
    print(f"  - Adjustments: {len(adjustments_data)} records")
    print()

    if not any([transactions_data, settlements_data, adjustments_data]):
        print("No data to seed. Please ensure JSON files exist in the data/ directory.")
        await engine.dispose()
        return

    # Parse data into schema objects
    print("Parsing data into schema objects...")
    transactions = parse_transactions(transactions_data)
    settlements = parse_settlements(settlements_data)
    adjustments = parse_adjustments(adjustments_data)

    print(f"Successfully parsed:")
    print(f"  - Transactions: {len(transactions)} records")
    print(f"  - Settlements: {len(settlements)} records")
    print(f"  - Adjustments: {len(adjustments)} records")
    print()

    # Ingest data using IngestionService
    print("Ingesting data into database...")
    print("-" * 40)

    async with async_session_maker() as session:
        ingestion_service = IngestionService(session)

        # Ingest transactions
        if transactions:
            print(f"Ingesting {len(transactions)} transactions...")
            txn_count, txn_errors = await ingestion_service.ingest_transactions(transactions)
            print(f"  - Ingested: {txn_count}")
            if txn_errors:
                print(f"  - Errors: {len(txn_errors)}")
                for err in txn_errors[:5]:  # Show first 5 errors
                    print(f"    - {err}")
                if len(txn_errors) > 5:
                    print(f"    - ... and {len(txn_errors) - 5} more errors")
        else:
            txn_count, txn_errors = 0, []

        # Ingest settlements
        if settlements:
            print(f"Ingesting {len(settlements)} settlements...")
            stl_count, stl_errors = await ingestion_service.ingest_settlements(settlements)
            print(f"  - Ingested: {stl_count}")
            if stl_errors:
                print(f"  - Errors: {len(stl_errors)}")
                for err in stl_errors[:5]:  # Show first 5 errors
                    print(f"    - {err}")
                if len(stl_errors) > 5:
                    print(f"    - ... and {len(stl_errors) - 5} more errors")
        else:
            stl_count, stl_errors = 0, []

        # Ingest adjustments
        if adjustments:
            print(f"Ingesting {len(adjustments)} adjustments...")
            adj_count, adj_errors = await ingestion_service.ingest_adjustments(adjustments)
            print(f"  - Ingested: {adj_count}")
            if adj_errors:
                print(f"  - Errors: {len(adj_errors)}")
                for err in adj_errors[:5]:  # Show first 5 errors
                    print(f"    - {err}")
                if len(adj_errors) > 5:
                    print(f"    - ... and {len(adj_errors) - 5} more errors")
        else:
            adj_count, adj_errors = 0, []

    # Print summary
    print()
    print("=" * 60)
    print("SEEDING SUMMARY")
    print("=" * 60)
    print()
    print(f"{'Record Type':<20} {'Loaded':<12} {'Ingested':<12} {'Errors':<12}")
    print("-" * 56)
    print(f"{'Transactions':<20} {len(transactions):<12} {txn_count:<12} {len(txn_errors):<12}")
    print(f"{'Settlements':<20} {len(settlements):<12} {stl_count:<12} {len(stl_errors):<12}")
    print(f"{'Adjustments':<20} {len(adjustments):<12} {adj_count:<12} {len(adj_errors):<12}")
    print("-" * 56)
    total_loaded = len(transactions) + len(settlements) + len(adjustments)
    total_ingested = txn_count + stl_count + adj_count
    total_errors = len(txn_errors) + len(stl_errors) + len(adj_errors)
    print(f"{'TOTAL':<20} {total_loaded:<12} {total_ingested:<12} {total_errors:<12}")
    print()

    if total_errors == 0:
        print("Database seeding completed successfully!")
    else:
        print(f"Database seeding completed with {total_errors} error(s).")
        print("Check the errors above for details.")

    # Cleanup
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
