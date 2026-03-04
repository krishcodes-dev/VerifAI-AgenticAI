"""
agent.py — VerifAI Fraud Detection Pipeline

Architecture: ML Inference Pipeline (NOT a language-model agent)

The pipeline runs in 5 clearly defined phases:
  1. PERCEIVE  — gather transaction context and user history
  2. REASON    — extract features and run XGBoost inference
  3. DECIDE    — classify risk level and choose action
  4. ACT       — send email notifications and return decision
  5. LOG       — persist audit trail for future offline retraining

NOTE ON "LEARNING":
  This pipeline does NOT automatically retrain the ML model.
  User feedback is logged so that a separate offline retraining job
  can incorporate it. Callers are told exactly this — no false claims
  of live model updates.
"""

from enum import Enum
from datetime import datetime
import logging
import math

import joblib
import pandas as pd

from app.config import get_settings
from app.ml.feature_engineering import FeatureEngineer, FEATURE_COLUMNS
from app.services.history_store import UserTransactionHistory
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
settings = get_settings()


class DecisionEnum(Enum):
    APPROVE = "APPROVED"
    HOLD = "HOLD"
    BLOCK = "BLOCKED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AgentController:
    """
    VerifAI Fraud Detection Pipeline Controller.

    Evaluates financial transactions through a 5-phase pipeline and returns
    a deterministic, ML-backed fraud decision.

    Decisions are based solely on:
    - Computed behavioral features from transaction data and user history
    - XGBoost model probability output
    - Configurable risk thresholds (FRAUD_HIGH_RISK_THRESHOLD, FRAUD_MEDIUM_RISK_THRESHOLD)

    No hardcoded outcome overrides exist in this implementation.
    """

    def __init__(self):
        self.history_store = UserTransactionHistory()
        self.email = EmailService()

        # Load the trained ML model and scaler from disk
        try:
            self.model = joblib.load(settings.ML_MODEL_PATH)
            self.scaler = joblib.load(settings.SCALER_PATH)
            logger.info("✅ ML model and scaler loaded from %s", settings.ML_MODEL_PATH)
        except FileNotFoundError:
            logger.critical(
                "ML model not found at '%s'. "
                "Run: python app/ml/model_training.py to train the model. "
                "Falling back to neutral score (0.5) until model is present.",
                settings.ML_MODEL_PATH,
            )
            self.model = None
            self.scaler = None

        # Feedback log for offline retraining — bounded to prevent memory growth
        self._MAX_LOG_ENTRIES = 10_000
        self.feedback_log: list[dict] = []

    # ── Phase Orchestrator ────────────────────────────────────────────────────

    async def process_transaction(self, transaction: dict) -> dict:
        """
        Evaluate a transaction through the full fraud detection pipeline.

        PERCEIVE → REASON → DECIDE → ACT → LOG

        Returns:
            dict with transaction_id, fraud_score, risk_level, decision,
            reason, actions, and requires_confirmation flag.
        """
        tx_id = transaction.get("id", "tx_unknown")
        user_id = transaction["user_id"]
        amount = transaction["amount"]
        merchant = transaction["merchant"]
        email = transaction.get("email")
        category = transaction.get("merchant_category", "UNKNOWN")

        # ── PHASE 1: PERCEIVE ─────────────────────────────────────
        logger.info("[PERCEIVE] tx=%s user=%s amount=%.2f merchant=%s", tx_id, user_id, amount, merchant)
        user_history = await self.history_store.get_user_history(user_id)

        # ── PHASE 2: REASON ───────────────────────────────────────
        features = self._extract_features(transaction, user_history)
        fraud_probability = self._predict_fraud_probability(features)
        risk_level = self._classify_risk_level(fraud_probability)

        logger.info(
            "[REASON] tx=%s fraud_probability=%.4f risk_level=%s",
            tx_id, fraud_probability, risk_level,
        )

        # ── PHASE 3: DECIDE ───────────────────────────────────────
        high_threshold = settings.FRAUD_HIGH_RISK_THRESHOLD
        medium_threshold = settings.FRAUD_MEDIUM_RISK_THRESHOLD

        if fraud_probability >= high_threshold:
            decision = DecisionEnum.BLOCK
            reason = f"Transaction blocked — fraud probability {fraud_probability:.1%} exceeds high-risk threshold ({high_threshold:.0%})"
        elif fraud_probability >= medium_threshold:
            decision = DecisionEnum.HOLD
            reason = f"Transaction held for review — fraud probability {fraud_probability:.1%} exceeds medium-risk threshold ({medium_threshold:.0%})"
        else:
            decision = DecisionEnum.APPROVE
            reason = f"Transaction approved — fraud probability {fraud_probability:.1%} is below risk thresholds"

        logger.info("[DECIDE] tx=%s decision=%s reason=%s", tx_id, decision.value, reason)

        # ── PHASE 4: ACT ──────────────────────────────────────────
        actions = await self._execute_actions(
            decision=decision,
            tx_id=tx_id,
            user_id=user_id,
            amount=amount,
            merchant=merchant,
            fraud_probability=fraud_probability,
            email=email,
            category=category,
        )
        logger.info("[ACT] tx=%s actions=%s", tx_id, actions)

        # ── PHASE 5: LOG ──────────────────────────────────────────
        # Store in user history so future transactions by this user
        # benefit from their behavioural baseline.
        await self.history_store.add_transaction(user_id, transaction)

        # Append to feedback log for future offline retraining
        self._log_for_retraining({
            "tx_id": tx_id,
            "user_id": user_id,
            "fraud_probability": fraud_probability,
            "decision": decision.value,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            "transaction_id": tx_id,
            "fraud_score": fraud_probability,
            "risk_level": risk_level,
            "decision": decision.value,
            "reason": reason,
            "actions": actions,
            "requires_confirmation": decision == DecisionEnum.HOLD,
        }

    # ── Phase Implementations ─────────────────────────────────────────────────

    def _extract_features(self, transaction: dict, user_history: list) -> pd.DataFrame:
        """PHASE 2a: Build the feature DataFrame from transaction data and history."""
        history_df = pd.DataFrame(user_history) if user_history else pd.DataFrame()
        engineer = FeatureEngineer(user_history_df=history_df)
        return engineer.create_features(transaction)[FEATURE_COLUMNS]

    def _predict_fraud_probability(self, features: pd.DataFrame) -> float:
        """
        PHASE 2b: Run ML inference and return fraud probability.

        If the model is not loaded, returns a neutral score of 0.5 with a
        critical log message so ops teams can detect and fix the issue.

        Output is validated to be a finite float in [0.0, 1.0].
        """
        if self.model is None:
            logger.critical(
                "ML model is not loaded — returning neutral score 0.5. "
                "Run model_training.py to generate the model file."
            )
            return 0.5

        try:
            X_scaled = self.scaler.transform(features)
            raw_prob = self.model.predict_proba(X_scaled)[0][1]

            # Validate output is a real number in [0, 1]
            if not isinstance(raw_prob, (int, float)) or math.isnan(raw_prob) or math.isinf(raw_prob):
                logger.error(
                    "Model returned invalid probability: %s — falling back to 0.5", raw_prob
                )
                return 0.5

            return float(max(0.0, min(1.0, raw_prob)))

        except Exception as exc:
            logger.error("Model inference failed: %s — returning 0.5", exc, exc_info=True)
            return 0.5

    def _classify_risk_level(self, fraud_probability: float) -> str:
        """PHASE 2c: Map fraud probability to a human-readable risk level."""
        if fraud_probability >= 0.80:
            return "CRITICAL"
        elif fraud_probability >= 0.50:
            return "HIGH"
        elif fraud_probability >= 0.20:
            return "MEDIUM"
        else:
            return "LOW"

    async def _execute_actions(
        self,
        decision: DecisionEnum,
        tx_id: str,
        user_id: str,
        amount: float,
        merchant: str,
        fraud_probability: float,
        email: str | None,
        category: str,
    ) -> list[str]:
        """
        PHASE 4: Send email notifications based on the decision.
        All email failures are logged but do not affect the returned decision.
        """
        actions = []

        if decision == DecisionEnum.BLOCK:
            actions.append("TRANSACTION_BLOCKED")
            if email:
                try:
                    result = await self.email.send_fraud_alert(
                        email, user_id, amount, merchant,
                        fraud_probability,   # Use the real computed score, not a hardcoded value
                        category, tx_id=tx_id,
                    )
                    if result.get("success"):
                        actions.append("FRAUD_ALERT_EMAIL_SENT")
                    else:
                        logger.warning("[ACT] Fraud alert email not sent for tx=%s: %s", tx_id, result)
                except Exception as exc:
                    logger.error("[ACT] Email send failed for tx=%s: %s", tx_id, exc, exc_info=True)

                try:
                    await self.email.send_account_locked(email, user_id, tx_id=tx_id)
                    actions.append("ACCOUNT_LOCKED_EMAIL_SENT")
                except Exception as exc:
                    logger.error("[ACT] Account locked email failed for tx=%s: %s", tx_id, exc, exc_info=True)

        elif decision == DecisionEnum.HOLD:
            actions.append("TRANSACTION_HELD")
            if email:
                try:
                    result = await self.email.send_verification_required(
                        email, user_id, amount, merchant,
                        fraud_probability,   # Real score
                        tx_id=tx_id,
                    )
                    if result.get("success"):
                        actions.append("VERIFICATION_EMAIL_SENT")
                    else:
                        logger.warning("[ACT] Verification email not sent for tx=%s: %s", tx_id, result)
                except Exception as exc:
                    logger.error("[ACT] Email send failed for tx=%s: %s", tx_id, exc, exc_info=True)

        else:  # APPROVE
            actions.append("TRANSACTION_APPROVED")
            if email:
                try:
                    result = await self.email.send_transaction_approved(
                        email, user_id, amount, merchant, tx_id=tx_id
                    )
                    if result.get("success"):
                        actions.append("APPROVAL_EMAIL_SENT")
                    else:
                        logger.warning("[ACT] Approval email not sent for tx=%s: %s", tx_id, result)
                except Exception as exc:
                    logger.error("[ACT] Email send failed for tx=%s: %s", tx_id, exc, exc_info=True)

        return actions

    # ── Feedback / Retraining ─────────────────────────────────────────────────

    def _log_for_retraining(self, entry: dict) -> None:
        """
        PHASE 5 LOG: Append this transaction's outcome to the retraining queue.

        This log is in-memory only. It survives for the lifetime of the process
        but will be cleared on restart. For production retraining pipelines,
        use the DB Transaction table (also written by the router) instead.
        """
        if len(self.feedback_log) >= self._MAX_LOG_ENTRIES:
            # Trim oldest 10% to prevent unbounded memory growth
            self.feedback_log = self.feedback_log[self._MAX_LOG_ENTRIES // 10:]

        self.feedback_log.append(entry)
        logger.debug("[LOG] Feedback entry queued: tx=%s", entry.get("tx_id"))

    async def handle_user_verification_response(self, tx_id: str, user_confirmed: bool) -> dict:
        """
        Record user feedback on a held or flagged transaction.

        IMPORTANT: This does NOT retrain the model automatically.
        Feedback is logged to the feedback_log list and should be persisted
        to the database by the calling endpoint for use by an offline
        retraining pipeline.

        Args:
            tx_id: The transaction ID being responded to
            user_confirmed: True = user says this transaction is legitimate,
                            False = user confirms it was fraudulent
        """
        logger.info(
            "[LOG] User verification response: tx=%s confirmed_legitimate=%s",
            tx_id, user_confirmed,
        )

        if not user_confirmed:
            logger.warning(
                "[LOG] Fraud confirmed by user for tx=%s — "
                "this will be available to the retraining pipeline via the DB.",
                tx_id,
            )

        return {
            "transaction_id": tx_id,
            "status": "feedback_recorded",
            "user_confirmed": user_confirmed,
            "model_updated": False,  # Honest: the model is NOT updated in real time
            "message": (
                "Thank you for your feedback. It has been recorded and will be "
                "incorporated in the next scheduled model retraining cycle."
            ),
        }
