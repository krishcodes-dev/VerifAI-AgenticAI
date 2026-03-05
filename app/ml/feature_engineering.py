"""
feature_engineering.py — VerifAI Transaction Feature Extractor

Generates the 15 behavioral and contextual features that the XGBoost model
uses for fraud probability estimation.

Correctness fixes applied:
  - merchant_seen_before: now checks if the specific merchant appears in history,
    not just whether any history exists at all.
  - has_vacation_pattern: removed (was always 0, dead feature). Column retained
    in FEATURE_COLUMNS to avoid breaking the trained model's feature expectation;
    it is permanently set to 0 as before, but is clearly marked as a placeholder.
  - Time features: now derive hour/day from the transaction's own timestamp
    (or creation timestamp) rather than the server's wall clock. This ensures
    batch-processed or replayed transactions get the correct temporal context.
  - transactions_today / is_new_device: these are still accepted from the
    transaction payload. Callers (e.g. the API router) are responsible for
    computing them from the user's session/history; they are no longer
    injected with hardcoded mock values.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional


class FeatureEngineer:
    """Extracts behavioral features for fraud detection from transaction data."""

    def __init__(self, user_history_df: Optional[pd.DataFrame] = None):
        self.user_history = user_history_df if user_history_df is not None else pd.DataFrame()

    def create_features(self, transaction: dict) -> pd.DataFrame:
        """
        Generate the 15-feature vector expected by the XGBoost model.

        Args:
            transaction: raw transaction dict from the API request

        Returns:
            Single-row DataFrame with all FEATURE_COLUMNS populated.
        """
        features: dict = {}

        # ── 1. AMOUNT FEATURES ────────────────────────────────────
        if len(self.user_history) > 0 and "amount" in self.user_history.columns:
            mean_amount = self.user_history["amount"].mean()
            std_amount = self.user_history["amount"].std()
        else:
            # No history yet — use population-level default estimates
            mean_amount = 5_000.0
            std_amount = 3_000.0

        tx_amount = float(transaction.get("amount", 5_000))
        features["amount_zscore"] = (tx_amount - mean_amount) / (std_amount + 1e-8)
        features["amount_ratio_to_avg"] = tx_amount / (mean_amount + 1.0)
        features["is_unusual_amount"] = 1 if tx_amount > (mean_amount + 3 * std_amount) else 0

        # ── 2. TIME FEATURES ──────────────────────────────────────
        # Use the transaction's own timestamp if provided.
        # This prevents batch / replayed transactions from inheriting the
        # server's current clock as their "hour of day".
        tx_timestamp_raw = transaction.get("timestamp")
        if tx_timestamp_raw:
            try:
                if isinstance(tx_timestamp_raw, str):
                    tx_time = datetime.fromisoformat(tx_timestamp_raw.replace("Z", "+00:00"))
                elif isinstance(tx_timestamp_raw, (int, float)):
                    tx_time = datetime.utcfromtimestamp(tx_timestamp_raw)
                else:
                    tx_time = tx_timestamp_raw  # assume already a datetime
            except (ValueError, TypeError):
                tx_time = datetime.utcnow()
        else:
            tx_time = datetime.utcnow()

        features["hour_of_day"] = tx_time.hour
        features["day_of_week"] = tx_time.weekday()
        features["is_night_transaction"] = 1 if (tx_time.hour >= 22 or tx_time.hour < 6) else 0
        features["is_weekend"] = 1 if tx_time.weekday() >= 5 else 0

        # ── 3. LOCATION FEATURES ──────────────────────────────────
        location_distance = float(transaction.get("location_distance", 0))
        features["location_distance_km"] = location_distance
        features["is_unusual_location"] = 1 if location_distance > 500 else 0

        # ── 4. FREQUENCY FEATURES ─────────────────────────────────
        # transactions_today should be computed from user history by the caller,
        # or passed directly from a session-level counter.
        # Fall back to counting from user_history if not provided.
        if "transactions_today" in transaction:
            transactions_today = int(transaction["transactions_today"])
        elif len(self.user_history) > 0 and "created_at" in self.user_history.columns:
            today = tx_time.date()
            try:
                daily_counts = self.user_history[
                    pd.to_datetime(self.user_history["created_at"]).dt.date == today
                ]
                transactions_today = len(daily_counts)
            except Exception:
                transactions_today = 1
        else:
            transactions_today = 1

        features["transactions_today"] = transactions_today
        features["is_velocity_attack"] = 1 if transactions_today > 10 else 0

        # ── 5. DEVICE FEATURES ────────────────────────────────────
        features["is_new_device"] = 1 if transaction.get("is_new_device", False) else 0

        # ── 6. MERCHANT FEATURES ──────────────────────────────────
        merchant_category = transaction.get("merchant_category", "").upper()
        features["is_high_risk_merchant_category"] = (
            1 if merchant_category in {"CRYPTO", "MONEY_TRANSFER", "GAMBLING"} else 0
        )

        # Semantic fix: check if this specific merchant has been seen before,
        # not just whether any history exists.
        tx_merchant = transaction.get("merchant", "").strip().lower()
        if len(self.user_history) > 0 and "merchant" in self.user_history.columns:
            seen_merchants = set(self.user_history["merchant"].str.strip().str.lower())
            features["merchant_seen_before"] = 1 if tx_merchant in seen_merchants else 0
        else:
            features["merchant_seen_before"] = 0

        # ── 7. CONTEXTUAL FEATURES ────────────────────────────────
        # has_vacation_pattern: placeholder feature — always 0.
        # Kept in the schema to match the trained model's feature vector.
        # A future improvement: implement geo-cluster analysis to detect
        # travel patterns from location history.
        features["has_vacation_pattern"] = 0

        return pd.DataFrame([features])


# The ordered list of feature columns the XGBoost model was trained on.
# This must match the column order used during model training exactly.
FEATURE_COLUMNS = [
    "amount_zscore",
    "amount_ratio_to_avg",
    "is_unusual_amount",
    "hour_of_day",
    "day_of_week",
    "is_night_transaction",
    "is_weekend",           # generated in the time block (right after is_night)
    "location_distance_km",
    "is_unusual_location",
    "transactions_today",
    "is_velocity_attack",
    "is_new_device",
    "is_high_risk_merchant_category",
    "merchant_seen_before",
    "has_vacation_pattern",
]
