from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Transaction, Settlement, Adjustment
from app.schemas.transaction import TransactionCreate
from app.schemas.settlement import SettlementCreate
from app.schemas.adjustment import AdjustmentCreate


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_transactions(
        self, transactions: list[TransactionCreate]
    ) -> tuple[int, list[str]]:
        """Ingest multiple transactions. Returns (count_ingested, errors)."""
        ingested = 0
        errors = []

        for txn in transactions:
            try:
                # Check if transaction already exists
                stmt = select(Transaction).where(
                    Transaction.transaction_id == txn.transaction_id
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    errors.append(f"Transaction {txn.transaction_id} already exists")
                    continue

                db_txn = Transaction(
                    transaction_id=txn.transaction_id,
                    merchant_order_id=txn.merchant_order_id,
                    amount=txn.amount,
                    currency=txn.currency.upper(),
                    timestamp=txn.timestamp,
                    status=txn.status,
                    customer_id=txn.customer_id,
                    country=txn.country.upper(),
                )
                self.db.add(db_txn)
                ingested += 1

            except Exception as e:
                errors.append(f"Error ingesting transaction {txn.transaction_id}: {str(e)}")

        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            errors.append(f"Database commit failed: {str(e)}")
        return ingested, errors

    async def ingest_settlements(
        self, settlements: list[SettlementCreate]
    ) -> tuple[int, list[str]]:
        """Ingest multiple settlements. Returns (count_ingested, errors)."""
        ingested = 0
        errors = []

        for stl in settlements:
            try:
                # Check if settlement already exists
                stmt = select(Settlement).where(
                    Settlement.settlement_reference == stl.settlement_reference
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    errors.append(f"Settlement {stl.settlement_reference} already exists")
                    continue

                db_stl = Settlement(
                    settlement_reference=stl.settlement_reference,
                    amount=stl.amount,
                    gross_amount=stl.gross_amount,
                    currency=stl.currency.upper(),
                    settlement_date=stl.settlement_date,
                    transaction_reference=stl.transaction_reference,
                    fees_deducted=stl.fees_deducted,
                    bank_name=stl.bank_name,
                )
                self.db.add(db_stl)
                ingested += 1

            except Exception as e:
                errors.append(f"Error ingesting settlement {stl.settlement_reference}: {str(e)}")

        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            errors.append(f"Database commit failed: {str(e)}")
        return ingested, errors

    async def ingest_adjustments(
        self, adjustments: list[AdjustmentCreate]
    ) -> tuple[int, list[str]]:
        """Ingest multiple adjustments. Returns (count_ingested, errors)."""
        ingested = 0
        errors = []

        for adj in adjustments:
            try:
                # Check if adjustment already exists
                stmt = select(Adjustment).where(
                    Adjustment.adjustment_id == adj.adjustment_id
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    errors.append(f"Adjustment {adj.adjustment_id} already exists")
                    continue

                db_adj = Adjustment(
                    adjustment_id=adj.adjustment_id,
                    transaction_reference=adj.transaction_reference,
                    amount=adj.amount,
                    currency=adj.currency.upper(),
                    type=adj.type,
                    date=adj.date,
                    reason_code=adj.reason_code,
                )
                self.db.add(db_adj)
                ingested += 1

            except Exception as e:
                errors.append(f"Error ingesting adjustment {adj.adjustment_id}: {str(e)}")

        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            errors.append(f"Database commit failed: {str(e)}")
        return ingested, errors
