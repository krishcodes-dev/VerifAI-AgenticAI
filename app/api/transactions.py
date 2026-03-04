from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import logging
from datetime import datetime
from typing import Optional

from app.services.agent import AgentController
from app.models.schemas import TransactionRequest
from app.models import Transaction, TransactionStatus, User
from app.database import get_db
from app.api.auth import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["transactions"])

# Module-level singleton — AgentController loads the ML model once at startup
agent = AgentController()


# ── Process Transaction ───────────────────────────────────────────────────────

@router.post("/transactions/process", response_model=dict)
async def process_transaction(
    request: TransactionRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Evaluate a financial transaction for fraud risk and take autonomous action.

    The authenticated user must match the user_id in the request body.
    Decision output: APPROVED | HOLD | BLOCKED

    Example request body:
    {
        "user_id": "your-user-uuid",
        "amount": 75000,
        "merchant": "Unknown_Store",
        "merchant_category": "CRYPTO",
        "device_type": "web",
        "device_ip": "192.168.1.100",
        "user_location": {"lat": 19.0760, "lon": 72.8777},
        "email": "you@example.com"
    }
    """
    # ── Ownership check ───────────────────────────────────────────
    # The requesting user can only process transactions for their own account.
    if request.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to process transactions for this user_id",
        )

    try:
        # Build the transaction dict for the agent pipeline
        tx_dict = request.dict()
        tx_id = str(uuid.uuid4())
        tx_dict["id"] = tx_id

        # ── Run agent pipeline ────────────────────────────────────
        result = await agent.process_transaction(tx_dict)

        # ── Persist result to database ────────────────────────────
        _persist_transaction(db, request, result, tx_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing transaction for user=%s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Transaction processing failed")


def _persist_transaction(
    db: Session,
    request: TransactionRequest,
    result: dict,
    tx_id: str,
) -> None:
    """
    Write the agent's decision to the transactions table.
    Non-fatal — logs on failure rather than crashing the response.
    """
    try:
        decision_str = result.get("decision", "APPROVED")
        # Map agent decision string to ORM enum
        decision_map = {
            "APPROVED": TransactionStatus.APPROVED,
            "HOLD": TransactionStatus.HOLD,
            "BLOCKED": TransactionStatus.BLOCKED,
            "MANUAL_REVIEW": TransactionStatus.FLAGGED,
        }
        decision_enum = decision_map.get(decision_str, TransactionStatus.FLAGGED)

        tx = Transaction(
            id=tx_id,
            user_id=request.user_id,
            amount=request.amount,
            merchant=request.merchant,
            category=request.merchant_category,
            fraud_score=result.get("fraud_score", 0.0),
            risk_level=result.get("risk_level", "UNKNOWN"),
            decision=decision_enum,
            device_ip=request.device_ip,
            device_type=request.device_type,
            processed_at=datetime.utcnow(),
        )
        db.add(tx)
        db.commit()
        logger.info("Persisted transaction id=%s decision=%s", tx_id, decision_str)

    except Exception as e:
        db.rollback()
        # Non-fatal — the fraud decision was already returned to the caller
        logger.error("Failed to persist transaction id=%s: %s", tx_id, e, exc_info=True)


# ── Transaction Status ────────────────────────────────────────────────────────

@router.get("/transactions/status/{transaction_id}")
async def get_transaction_status(
    transaction_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve the persisted status of a specific transaction."""
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Ownership check — users can only view their own transactions
    if tx.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "transaction_id": tx.id,
        "status": tx.decision.value if tx.decision else "UNKNOWN",
        "fraud_score": tx.fraud_score,
        "risk_level": tx.risk_level,
        "amount": tx.amount,
        "merchant": tx.merchant,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "processed_at": tx.processed_at.isoformat() if tx.processed_at else None,
    }


# ── Transaction List ──────────────────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    """
    Return paginated list of transactions for the authenticated user.
    Optionally filter by status: APPROVED | HOLD | BLOCKED | FLAGGED
    """
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    if status_filter:
        try:
            status_enum = TransactionStatus(status_filter.upper())
            query = query.filter(Transaction.decision == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter: {status_filter}. Valid values: APPROVED, HOLD, BLOCKED, FLAGGED",
            )

    total = query.count()
    transactions = (
        query.order_by(Transaction.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "merchant": tx.merchant,
                "category": tx.category,
                "fraud_score": tx.fraud_score,
                "risk_level": tx.risk_level,
                "status": tx.decision.value if tx.decision else "UNKNOWN",
                "device_type": tx.device_type,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in transactions
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    }


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@router.get("/transactions/stats")
async def get_transaction_stats(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Return summary statistics for the authenticated user's transactions.
    Used by the dashboard to populate stat cards and charts.
    """
    base_q = db.query(Transaction).filter(Transaction.user_id == user_id)

    total = base_q.count()
    blocked = base_q.filter(Transaction.decision == TransactionStatus.BLOCKED).count()
    held = base_q.filter(Transaction.decision == TransactionStatus.HOLD).count()
    approved = base_q.filter(Transaction.decision == TransactionStatus.APPROVED).count()

    avg_score_row = db.query(func.avg(Transaction.fraud_score)).filter(
        Transaction.user_id == user_id
    ).scalar()
    avg_fraud_score = round(float(avg_score_row or 0), 4)

    # Risk distribution buckets
    buckets = [
        {"name": "0–20", "min": 0.0, "max": 0.2},
        {"name": "20–40", "min": 0.2, "max": 0.4},
        {"name": "40–60", "min": 0.4, "max": 0.6},
        {"name": "60–80", "min": 0.6, "max": 0.8},
        {"name": "80–100", "min": 0.8, "max": 1.01},
    ]
    risk_distribution = []
    for b in buckets:
        count = base_q.filter(
            Transaction.fraud_score >= b["min"],
            Transaction.fraud_score < b["max"],
        ).count()
        risk_distribution.append({"name": b["name"], "value": count})

    return {
        "total_transactions": total,
        "blocked": blocked,
        "held": held,
        "approved": approved,
        "avg_fraud_score": avg_fraud_score,
        "fraud_rate": round(blocked / total, 4) if total > 0 else 0.0,
        "risk_distribution": risk_distribution,
    }


# ── User Verification Feedback ────────────────────────────────────────────────

@router.post("/transactions/verify/{transaction_id}")
async def verify_transaction(
    transaction_id: str,
    user_confirmed: bool,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Record user feedback on whether a held/flagged transaction is legitimate.
    NOTE: This stores the feedback but does not retrain the model automatically.
    Retraining is a separate offline process.
    """
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await agent.handle_user_verification_response(transaction_id, user_confirmed)
    return result
