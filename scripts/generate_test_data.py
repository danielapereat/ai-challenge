#!/usr/bin/env python3
"""
Payment Reconciliation Engine - Test Data Generator

Generates realistic test data for payment reconciliation testing with intentional
edge cases for matching algorithms.

Generated datasets:
- 200 transactions over 30 days (70 MXN, 70 COP, 60 BRL)
- 180 settlements with various matching scenarios
- 20 adjustments (refunds and chargebacks)

Intentional edge cases included for testing reconciliation logic.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from faker import Faker

# Initialize Faker with locales for realistic data
fake = Faker(['en_US', 'es_MX', 'es_CO', 'pt_BR'])
Faker.seed(42)
random.seed(42)

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Currency configurations with exchange rates to USD
CURRENCIES = {
    "MXN": {"count": 70, "rate_to_usd": 17.5, "min_amount": 175, "max_amount": 87500},
    "COP": {"count": 70, "rate_to_usd": 4000, "min_amount": 40000, "max_amount": 20000000},
    "BRL": {"count": 60, "rate_to_usd": 5.0, "min_amount": 50, "max_amount": 25000},
}

# Transaction status distribution
STATUS_DISTRIBUTION = {
    "captured": 180,
    "authorized": 15,
    "failed": 5,
}

# Provider configurations
PROVIDERS = ["stripe", "adyen", "payu", "mercadopago", "dlocal"]
PAYMENT_METHODS = ["card", "pix", "pse", "oxxo", "boleto", "spei"]


def generate_transaction_id() -> str:
    """Generate a unique transaction ID."""
    return f"txn_{uuid.uuid4().hex[:16]}"


def generate_provider_reference() -> str:
    """Generate a provider-specific reference."""
    return f"prov_{uuid.uuid4().hex[:12]}"


def generate_merchant_reference() -> str:
    """Generate a merchant order reference."""
    return f"order_{fake.random_number(digits=8, fix_len=True)}"


def truncate_reference(ref: str, truncate_type: str = "random") -> str:
    """Truncate or modify a reference for edge case testing."""
    if truncate_type == "truncate":
        # Truncate to random shorter length
        return ref[:random.randint(8, len(ref) - 4)]
    elif truncate_type == "prefix":
        # Add spurious prefix
        return f"dup_{ref}"
    elif truncate_type == "suffix":
        # Truncate suffix
        return ref[:-random.randint(2, 5)]
    return ref


def generate_amount_in_currency(currency: str) -> Decimal:
    """Generate a random amount in the specified currency within $10-$5000 USD equivalent."""
    config = CURRENCIES[currency]
    amount = Decimal(random.uniform(config["min_amount"], config["max_amount"]))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_fee_deduction(amount: Decimal, fee_percentage: float) -> Decimal:
    """Apply a fee deduction to an amount."""
    fee = amount * Decimal(str(fee_percentage / 100))
    return (amount - fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_transactions(start_date: datetime, days: int = 30) -> list[dict[str, Any]]:
    """
    Generate 200 transactions over 30 days.

    Distribution:
    - 70 MXN, 70 COP, 60 BRL
    - 180 captured, 15 authorized-only, 5 failed
    """
    transactions = []

    # Create currency pool
    currency_pool = []
    for currency, config in CURRENCIES.items():
        currency_pool.extend([currency] * config["count"])
    random.shuffle(currency_pool)

    # Create status pool
    status_pool = []
    for status, count in STATUS_DISTRIBUTION.items():
        status_pool.extend([status] * count)
    random.shuffle(status_pool)

    for i in range(200):
        currency = currency_pool[i]
        status = status_pool[i]

        # Random date within the 30-day period
        transaction_date = start_date + timedelta(
            days=random.randint(0, days - 1),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )

        txn_id = generate_transaction_id()
        provider_ref = generate_provider_reference()
        merchant_ref = generate_merchant_reference()
        amount = generate_amount_in_currency(currency)

        transaction = {
            "transaction_id": txn_id,
            "provider_reference": provider_ref,
            "merchant_reference": merchant_ref,
            "amount": str(amount),
            "currency": currency,
            "status": status,
            "provider": random.choice(PROVIDERS),
            "payment_method": random.choice(PAYMENT_METHODS),
            "created_at": transaction_date.isoformat(),
            "captured_at": (transaction_date + timedelta(minutes=random.randint(1, 30))).isoformat() if status == "captured" else None,
            "customer_email": fake.email(),
            "customer_name": fake.name(),
            "description": fake.sentence(nb_words=5),
            "metadata": {
                "ip_address": fake.ipv4(),
                "user_agent": fake.user_agent(),
                "country": random.choice(["MX", "CO", "BR"]),
            }
        }

        transactions.append(transaction)

    # Sort by created_at
    transactions.sort(key=lambda x: x["created_at"])

    return transactions


def generate_settlements(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Generate 180 settlements with various matching scenarios.

    Distribution:
    - 165 clean matches (after accounting for overlaps)
    - 10 with fee deductions (2-5% less)
    - 5 with date offsets (2-3 days after capture)
    - 5 orphan settlements (no matching transaction)
    - 3 with truncated/modified references
    - 3 cross-currency (BRL -> USD)

    Target: 90% match rate (165 clean + special cases = ~175 matched, 5 orphans)
    Leave 5-10 captured transactions without settlements (missing money edge case)
    """
    settlements = []

    # Get only captured transactions for settlement matching
    captured_txns = [t for t in transactions if t["status"] == "captured"]

    # Separate BRL transactions for cross-currency cases
    brl_txns = [t for t in captured_txns if t["currency"] == "BRL"]
    other_txns = [t for t in captured_txns if t["currency"] != "BRL"]

    # We need 175 matched settlements + 5 orphans = 180 total
    # Leave 5-10 captured transactions without settlements
    # So we use 175 transactions for settlement creation

    # Reserve 3 BRL transactions for cross-currency
    cross_currency_txns = brl_txns[:3]
    remaining_brl = brl_txns[3:]

    # Combine remaining transactions
    txns_for_settlement = other_txns + remaining_brl
    random.shuffle(txns_for_settlement)

    # Take 172 (175 - 3 cross-currency) from the pool
    txns_for_settlement = txns_for_settlement[:172]

    # Track which transactions get settlements
    settlement_txn_indices = list(range(len(txns_for_settlement)))
    random.shuffle(settlement_txn_indices)

    # Indices for special cases (non-overlapping for clear categorization)
    fee_deduction_indices = set(settlement_txn_indices[:10])  # 10 with fee deductions
    date_offset_indices = set(settlement_txn_indices[10:25])  # 15 with date offsets
    truncated_ref_indices = set(settlement_txn_indices[25:30])  # 5 truncated refs

    settlement_count = 0

    for idx, txn in enumerate(txns_for_settlement):
        if settlement_count >= 172:  # 175 matched - 3 cross-currency
            break

        settlement_id = f"stl_{uuid.uuid4().hex[:16]}"

        # Base settlement date (same day or next day for clean matches)
        txn_date = datetime.fromisoformat(txn["captured_at"]) if txn["captured_at"] else datetime.fromisoformat(txn["created_at"])

        # Determine settlement characteristics
        amount = Decimal(txn["amount"])
        currency = txn["currency"]
        reference = txn["provider_reference"]
        settlement_date = txn_date + timedelta(hours=random.randint(12, 36))

        # Apply special case modifications
        fee_applied = None
        date_offset_days = 0
        reference_modification = None
        cross_currency = False

        if idx in fee_deduction_indices:
            # Fee deduction case: 2-5% less
            fee_percentage = random.uniform(2.0, 5.0)
            amount = apply_fee_deduction(amount, fee_percentage)
            fee_applied = round(fee_percentage, 2)

        if idx in date_offset_indices:
            # Date offset case: 2-3 days after
            date_offset_days = random.randint(2, 3)
            settlement_date = txn_date + timedelta(days=date_offset_days)

        if idx in truncated_ref_indices:
            # Truncated reference case
            mod_type = random.choice(["truncate", "prefix", "suffix"])
            reference = truncate_reference(txn["provider_reference"], mod_type)
            reference_modification = mod_type

        settlement = {
            "settlement_id": settlement_id,
            "provider_reference": reference,
            "transaction_reference": txn["transaction_id"] if random.random() > 0.1 else None,
            "amount": str(amount),
            "currency": currency,
            "original_currency": txn["currency"] if cross_currency else None,
            "original_amount": txn["amount"] if cross_currency else None,
            "settlement_date": settlement_date.isoformat(),
            "provider": txn["provider"],
            "batch_id": f"batch_{settlement_date.strftime('%Y%m%d')}_{random.randint(1, 5)}",
            "status": "completed",
            "fee_applied": fee_applied,
            "date_offset_days": date_offset_days if date_offset_days > 0 else None,
            "reference_modification": reference_modification,
            "cross_currency": cross_currency,
            "metadata": {
                "payout_account": fake.iban(),
                "processing_fee": str(Decimal(random.uniform(0.1, 2.0)).quantize(Decimal("0.01"))),
            }
        }

        settlements.append(settlement)
        settlement_count += 1

    # Add 3 cross-currency settlements (BRL -> USD)
    for txn in cross_currency_txns:
        settlement_id = f"stl_{uuid.uuid4().hex[:16]}"
        txn_date = datetime.fromisoformat(txn["captured_at"]) if txn["captured_at"] else datetime.fromisoformat(txn["created_at"])
        settlement_date = txn_date + timedelta(hours=random.randint(12, 36))

        # Convert BRL to USD
        brl_amount = Decimal(txn["amount"])
        usd_amount = (brl_amount / Decimal(str(CURRENCIES["BRL"]["rate_to_usd"]))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        settlement = {
            "settlement_id": settlement_id,
            "provider_reference": txn["provider_reference"],
            "transaction_reference": txn["transaction_id"] if random.random() > 0.1 else None,
            "amount": str(usd_amount),
            "currency": "USD",
            "original_currency": "BRL",
            "original_amount": txn["amount"],
            "settlement_date": settlement_date.isoformat(),
            "provider": txn["provider"],
            "batch_id": f"batch_{settlement_date.strftime('%Y%m%d')}_{random.randint(1, 5)}",
            "status": "completed",
            "fee_applied": None,
            "date_offset_days": None,
            "reference_modification": None,
            "cross_currency": True,
            "metadata": {
                "payout_account": fake.iban(),
                "processing_fee": str(Decimal(random.uniform(0.1, 2.0)).quantize(Decimal("0.01"))),
                "exchange_rate": str(CURRENCIES["BRL"]["rate_to_usd"]),
            }
        }

        settlements.append(settlement)

    # Add 5 orphan settlements (no matching transaction)
    orphan_start_date = datetime.fromisoformat(transactions[0]["created_at"])
    for i in range(5):
        orphan_date = orphan_start_date + timedelta(days=random.randint(5, 25))
        orphan_currency = random.choice(list(CURRENCIES.keys()))
        orphan_amount = generate_amount_in_currency(orphan_currency)

        settlement = {
            "settlement_id": f"stl_{uuid.uuid4().hex[:16]}",
            "provider_reference": generate_provider_reference(),
            "transaction_reference": None,
            "amount": str(orphan_amount),
            "currency": orphan_currency,
            "original_currency": None,
            "original_amount": None,
            "settlement_date": orphan_date.isoformat(),
            "provider": random.choice(PROVIDERS),
            "batch_id": f"batch_{orphan_date.strftime('%Y%m%d')}_{random.randint(1, 5)}",
            "status": "completed",
            "fee_applied": None,
            "date_offset_days": None,
            "reference_modification": None,
            "cross_currency": False,
            "is_orphan": True,
            "metadata": {
                "payout_account": fake.iban(),
                "processing_fee": str(Decimal(random.uniform(0.1, 2.0)).quantize(Decimal("0.01"))),
                "note": "No matching transaction found - potential duplicate or mystery deposit",
            }
        }

        settlements.append(settlement)

    # Sort by settlement_date
    settlements.sort(key=lambda x: x["settlement_date"])

    return settlements


def generate_adjustments(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Generate 20 adjustments (refunds and chargebacks).

    Distribution:
    - 12 refunds (all matchable to transactions)
    - 8 chargebacks (5 matchable, 3 orphaned)
    """
    adjustments = []

    # Get captured transactions for adjustment matching
    captured_txns = [t for t in transactions if t["status"] == "captured"]
    random.shuffle(captured_txns)

    # Select transactions for refunds (12 matchable)
    refund_txns = captured_txns[:12]

    # Select transactions for chargebacks (5 matchable)
    chargeback_txns = captured_txns[12:17]

    # Generate refunds
    for txn in refund_txns:
        txn_date = datetime.fromisoformat(txn["captured_at"]) if txn["captured_at"] else datetime.fromisoformat(txn["created_at"])
        adjustment_date = txn_date + timedelta(days=random.randint(1, 14))

        # Refund amount: full or partial
        original_amount = Decimal(txn["amount"])
        if random.random() > 0.7:
            # Partial refund (30-80%)
            refund_amount = (original_amount * Decimal(str(random.uniform(0.3, 0.8)))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            refund_type = "partial"
        else:
            refund_amount = original_amount
            refund_type = "full"

        adjustment = {
            "adjustment_id": f"adj_{uuid.uuid4().hex[:16]}",
            "type": "refund",
            "refund_type": refund_type,
            "transaction_id": txn["transaction_id"],
            "provider_reference": txn["provider_reference"],
            "original_amount": str(original_amount),
            "adjustment_amount": str(refund_amount),
            "currency": txn["currency"],
            "adjustment_date": adjustment_date.isoformat(),
            "provider": txn["provider"],
            "reason": random.choice([
                "customer_request",
                "duplicate_charge",
                "product_not_received",
                "product_defective",
                "merchant_error",
            ]),
            "status": "completed",
            "is_orphan": False,
            "metadata": {
                "initiated_by": random.choice(["customer", "merchant", "system"]),
                "refund_method": random.choice(["original_method", "store_credit", "bank_transfer"]),
            }
        }

        adjustments.append(adjustment)

    # Generate matchable chargebacks (5)
    for txn in chargeback_txns:
        txn_date = datetime.fromisoformat(txn["captured_at"]) if txn["captured_at"] else datetime.fromisoformat(txn["created_at"])
        adjustment_date = txn_date + timedelta(days=random.randint(7, 45))

        adjustment = {
            "adjustment_id": f"adj_{uuid.uuid4().hex[:16]}",
            "type": "chargeback",
            "refund_type": None,
            "transaction_id": txn["transaction_id"],
            "provider_reference": txn["provider_reference"],
            "original_amount": txn["amount"],
            "adjustment_amount": txn["amount"],
            "currency": txn["currency"],
            "adjustment_date": adjustment_date.isoformat(),
            "provider": txn["provider"],
            "reason": random.choice([
                "fraud",
                "unrecognized_charge",
                "product_not_received",
                "credit_not_processed",
                "duplicate_processing",
            ]),
            "status": random.choice(["pending", "won", "lost"]),
            "is_orphan": False,
            "chargeback_code": f"CB{random.randint(1000, 9999)}",
            "metadata": {
                "card_network": random.choice(["visa", "mastercard", "amex"]),
                "dispute_deadline": (adjustment_date + timedelta(days=30)).isoformat(),
                "evidence_submitted": random.choice([True, False]),
            }
        }

        adjustments.append(adjustment)

    # Generate orphaned chargebacks (3) - can't link back to any transaction
    start_date = datetime.fromisoformat(transactions[0]["created_at"])
    for i in range(3):
        orphan_date = start_date + timedelta(days=random.randint(10, 25))
        orphan_currency = random.choice(list(CURRENCIES.keys()))
        orphan_amount = generate_amount_in_currency(orphan_currency)

        adjustment = {
            "adjustment_id": f"adj_{uuid.uuid4().hex[:16]}",
            "type": "chargeback",
            "refund_type": None,
            "transaction_id": None,
            "provider_reference": generate_provider_reference(),
            "original_amount": str(orphan_amount),
            "adjustment_amount": str(orphan_amount),
            "currency": orphan_currency,
            "adjustment_date": orphan_date.isoformat(),
            "provider": random.choice(PROVIDERS),
            "reason": random.choice([
                "fraud",
                "unrecognized_charge",
            ]),
            "status": "pending",
            "is_orphan": True,
            "chargeback_code": f"CB{random.randint(1000, 9999)}",
            "metadata": {
                "card_network": random.choice(["visa", "mastercard", "amex"]),
                "dispute_deadline": (orphan_date + timedelta(days=30)).isoformat(),
                "evidence_submitted": False,
                "note": "Cannot link to original transaction - orphaned chargeback",
            }
        }

        adjustments.append(adjustment)

    # Sort by adjustment_date
    adjustments.sort(key=lambda x: x["adjustment_date"])

    return adjustments


def generate_summary(
    transactions: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    adjustments: list[dict[str, Any]]
) -> dict[str, Any]:
    """Generate a summary of the generated data for verification."""

    # Transaction stats
    txn_by_currency = {}
    txn_by_status = {}
    for txn in transactions:
        currency = txn["currency"]
        status = txn["status"]
        txn_by_currency[currency] = txn_by_currency.get(currency, 0) + 1
        txn_by_status[status] = txn_by_status.get(status, 0) + 1

    # Settlement stats
    settlements_with_fee = sum(1 for s in settlements if s.get("fee_applied"))
    settlements_with_date_offset = sum(1 for s in settlements if s.get("date_offset_days"))
    settlements_with_ref_mod = sum(1 for s in settlements if s.get("reference_modification"))
    settlements_cross_currency = sum(1 for s in settlements if s.get("cross_currency"))
    settlements_orphan = sum(1 for s in settlements if s.get("is_orphan"))

    # Adjustment stats
    refunds = [a for a in adjustments if a["type"] == "refund"]
    chargebacks = [a for a in adjustments if a["type"] == "chargeback"]
    orphan_chargebacks = sum(1 for a in chargebacks if a.get("is_orphan"))

    # Calculate transactions without settlements
    settled_txn_ids = set()
    for s in settlements:
        if s.get("transaction_reference"):
            settled_txn_ids.add(s["transaction_reference"])

    captured_txns = [t for t in transactions if t["status"] == "captured"]
    txns_without_settlement = sum(1 for t in captured_txns if t["transaction_id"] not in settled_txn_ids)

    return {
        "generated_at": datetime.now().isoformat(),
        "transactions": {
            "total": len(transactions),
            "by_currency": txn_by_currency,
            "by_status": txn_by_status,
        },
        "settlements": {
            "total": len(settlements),
            "with_fee_deduction": settlements_with_fee,
            "with_date_offset": settlements_with_date_offset,
            "with_modified_reference": settlements_with_ref_mod,
            "cross_currency": settlements_cross_currency,
            "orphan": settlements_orphan,
            "clean_matches": len(settlements) - settlements_with_fee - settlements_with_date_offset - settlements_with_ref_mod - settlements_cross_currency - settlements_orphan,
        },
        "adjustments": {
            "total": len(adjustments),
            "refunds": len(refunds),
            "chargebacks": len(chargebacks),
            "orphan_chargebacks": orphan_chargebacks,
        },
        "edge_cases": {
            "transactions_without_settlement": txns_without_settlement,
            "settlements_without_transaction": settlements_orphan,
            "orphan_chargebacks": orphan_chargebacks,
            "fee_variance_records": settlements_with_fee,
            "date_offset_records": settlements_with_date_offset,
            "truncated_reference_records": settlements_with_ref_mod,
            "cross_currency_records": settlements_cross_currency,
        }
    }


def main():
    """Main function to generate all test data."""
    print("Payment Reconciliation Engine - Test Data Generator")
    print("=" * 55)

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Set start date (30 days ago from "today")
    start_date = datetime(2025, 1, 1, 0, 0, 0)

    print(f"\nGenerating data for 30-day period starting {start_date.date()}...")

    # Generate transactions
    print("\n1. Generating transactions...")
    transactions = generate_transactions(start_date, days=30)
    print(f"   Generated {len(transactions)} transactions")

    # Generate settlements
    print("\n2. Generating settlements...")
    settlements = generate_settlements(transactions)
    print(f"   Generated {len(settlements)} settlements")

    # Generate adjustments
    print("\n3. Generating adjustments...")
    adjustments = generate_adjustments(transactions)
    print(f"   Generated {len(adjustments)} adjustments")

    # Generate summary
    print("\n4. Generating summary...")
    summary = generate_summary(transactions, settlements, adjustments)

    # Save to files
    print("\n5. Saving files...")

    transactions_file = DATA_DIR / "transactions.json"
    with open(transactions_file, "w") as f:
        json.dump(transactions, f, indent=2)
    print(f"   Saved: {transactions_file}")

    settlements_file = DATA_DIR / "settlements.json"
    with open(settlements_file, "w") as f:
        json.dump(settlements, f, indent=2)
    print(f"   Saved: {settlements_file}")

    adjustments_file = DATA_DIR / "adjustments.json"
    with open(adjustments_file, "w") as f:
        json.dump(adjustments, f, indent=2)
    print(f"   Saved: {adjustments_file}")

    summary_file = DATA_DIR / "data_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"   Saved: {summary_file}")

    # Print summary
    print("\n" + "=" * 55)
    print("DATA GENERATION SUMMARY")
    print("=" * 55)

    print(f"\nTransactions: {summary['transactions']['total']}")
    print(f"  By currency: {summary['transactions']['by_currency']}")
    print(f"  By status: {summary['transactions']['by_status']}")

    print(f"\nSettlements: {summary['settlements']['total']}")
    print(f"  Clean matches: {summary['settlements']['clean_matches']}")
    print(f"  With fee deduction: {summary['settlements']['with_fee_deduction']}")
    print(f"  With date offset: {summary['settlements']['with_date_offset']}")
    print(f"  With modified reference: {summary['settlements']['with_modified_reference']}")
    print(f"  Cross-currency: {summary['settlements']['cross_currency']}")
    print(f"  Orphan (no transaction): {summary['settlements']['orphan']}")

    print(f"\nAdjustments: {summary['adjustments']['total']}")
    print(f"  Refunds: {summary['adjustments']['refunds']}")
    print(f"  Chargebacks: {summary['adjustments']['chargebacks']}")
    print(f"  Orphan chargebacks: {summary['adjustments']['orphan_chargebacks']}")

    print("\nEdge Cases Generated:")
    for case, count in summary['edge_cases'].items():
        print(f"  {case.replace('_', ' ').title()}: {count}")

    print("\n" + "=" * 55)
    print("Test data generation complete!")
    print(f"Files saved to: {DATA_DIR}")
    print("=" * 55)


if __name__ == "__main__":
    main()
