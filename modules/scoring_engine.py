"""
modules/scoring_engine.py
Slot quality scoring and classification.

Formula:
  slot_score = (norm_freq × 0.40)
             + (diversity  × 0.25)
             + ((1 − cancel_rate) × 0.20)
             + ((1 − noshow_rate) × 0.15)

Classification:
  > 0.65  → green  (recommended)
  0.40–0.65 → amber (marginal)
  < 0.40  → red   (not recommended)
"""

import pandas as pd
import numpy as np

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _align(pivot: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Reindex pivot to match reference index and columns, filling missing with 0."""
    return pivot.reindex(index=reference.index, columns=reference.columns, fill_value=0)


def calculate_slot_scores(
    freq_pivot: pd.DataFrame,
    cancel_pivot: pd.DataFrame,
    noshow_pivot: pd.DataFrame,
    diversity_pivot: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns a DataFrame of slot quality scores (0–1) with the same
    shape as freq_pivot (rows=time_slot, cols=day_name).
    """
    if freq_pivot.empty:
        return pd.DataFrame()

    cancel = _align(cancel_pivot, freq_pivot) if not cancel_pivot.empty else pd.DataFrame(0, index=freq_pivot.index, columns=freq_pivot.columns)
    noshow = _align(noshow_pivot, freq_pivot) if not noshow_pivot.empty else pd.DataFrame(0, index=freq_pivot.index, columns=freq_pivot.columns)
    diversity = _align(diversity_pivot, freq_pivot) if not diversity_pivot.empty else pd.DataFrame(0, index=freq_pivot.index, columns=freq_pivot.columns)

    # Normalise frequency 0–1
    max_freq = freq_pivot.values.max()
    norm_freq = freq_pivot / max_freq if max_freq > 0 else freq_pivot.copy()

    # Clip inputs to valid range
    cancel = cancel.clip(0, 1)
    noshow = noshow.clip(0, 1)
    diversity = diversity.clip(0, 1)

    score = (
        norm_freq * 0.40
        + diversity * 0.25
        + (1 - cancel) * 0.20
        + (1 - noshow) * 0.15
    )
    return score.clip(0, 1)


def classify_slots(score_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a DataFrame of the same shape with string labels:
    'green' | 'amber' | 'red'
    """
    if score_df.empty:
        return pd.DataFrame()

    def _label(v: float) -> str:
        if v > 0.65:
            return "green"
        if v >= 0.40:
            return "amber"
        return "red"

    # pandas >= 2.1 uses .map(); older versions use .applymap()
    mapper = getattr(score_df, "map", None) or score_df.applymap
    return mapper(_label)


def get_top_slots(score_df: pd.DataFrame, day: str, n: int = 5) -> pd.DataFrame:
    """
    Returns the top-N time slots ranked by quality score for a given day.
    Returns a DataFrame with columns: time_slot, score, rank.
    """
    if score_df.empty or day not in score_df.columns:
        return pd.DataFrame(columns=["time_slot", "score", "rank"])

    day_scores = score_df[[day]].reset_index()
    day_scores.columns = ["time_slot", "score"]
    day_scores = day_scores.sort_values("score", ascending=False).head(n).reset_index(drop=True)
    day_scores["rank"] = day_scores.index + 1
    return day_scores


def build_quality_table(
    score_df: pd.DataFrame,
    freq_pivot: pd.DataFrame,
    cancel_pivot: pd.DataFrame,
    diversity_pivot: pd.DataFrame,
    classification_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns a ranked flat table of all slot-day combinations with their metrics.
    Columns: Day, Time Slot, Quality Score, Booking Frequency,
             Cancellation Rate, Diversity Score, Classification.
    """
    records = []
    for time_slot in score_df.index:
        for day in score_df.columns:
            score = score_df.loc[time_slot, day]
            freq = freq_pivot.loc[time_slot, day] if (not freq_pivot.empty and time_slot in freq_pivot.index and day in freq_pivot.columns) else 0
            cancel = cancel_pivot.loc[time_slot, day] if (not cancel_pivot.empty and time_slot in cancel_pivot.index and day in cancel_pivot.columns) else 0
            diversity = diversity_pivot.loc[time_slot, day] if (not diversity_pivot.empty and time_slot in diversity_pivot.index and day in diversity_pivot.columns) else 0
            classification = classification_df.loc[time_slot, day] if (not classification_df.empty and time_slot in classification_df.index and day in classification_df.columns) else "red"

            records.append({
                "Day": day,
                "Time Slot": time_slot,
                "Quality Score": round(float(score), 3),
                "Booking Frequency": round(float(freq), 1),
                "Cancellation Rate": f"{float(cancel) * 100:.1f}%",
                "Diversity Score": round(float(diversity), 3),
                "Classification": classification,
            })

    result = pd.DataFrame(records)
    if not result.empty:
        result = result.sort_values("Quality Score", ascending=False).reset_index(drop=True)
    return result
