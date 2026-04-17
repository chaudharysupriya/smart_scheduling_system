"""
modules/simulation.py
Simulation engine: generates synthetic booking requests and routes them
through Fixed and Behaviour-Based schedules to compare performance.
"""

import pandas as pd
import numpy as np

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
]


def generate_requests(
    df_historical: pd.DataFrame,
    num_weeks: int = 6,
    seed: int = 42,
) -> list:
    """
    Creates a list of booking request dicts for the given number of weeks.
    Demand probabilities are derived from historical slot frequencies.
    Each request: {week, day, time_slot, customer_id}
    """
    rng = np.random.default_rng(seed)

    if df_historical.empty:
        requests = []
        for week in range(1, num_weeks + 1):
            for day in DAY_ORDER[:5]:
                n = rng.integers(3, 8)
                for _ in range(int(n)):
                    slot = rng.choice(TIME_SLOTS[:8])
                    requests.append({"week": week, "day": day, "time_slot": slot,
                                     "customer_id": f"C{rng.integers(1, 200):04d}"})
        return requests

    # Build probability distribution from historical demand
    demand = (
        df_historical.groupby(["day_name", "time_slot"])
        .size()
        .reset_index(name="count")
    )
    total = demand["count"].sum()
    demand["prob"] = demand["count"] / total if total > 0 else 1 / len(demand)

    # Average weekly booking volume (with 20 % uplift to stress-test capacity)
    years = max(df_historical["year"].nunique(), 1)
    # approximate: dataset spans ~years × 52 weeks
    avg_per_week = len(df_historical) / (years * 52)
    weekly_n = max(int(avg_per_week * 1.2), 5)

    requests = []
    for week in range(1, num_weeks + 1):
        n = int(rng.poisson(weekly_n))
        idx = rng.choice(len(demand), size=n, p=demand["prob"].values, replace=True)
        sampled = demand.iloc[idx]
        for _, row in sampled.iterrows():
            requests.append({
                "week": week,
                "day": row["day_name"],
                "time_slot": row["time_slot"],
                "customer_id": f"SIM{rng.integers(1, 1000):04d}",
            })

    return requests


def run_simulation(requests: list, schedule_df: pd.DataFrame) -> dict:
    """
    Routes each request through the given schedule.
    Returns a dict keyed by week number, each value containing:
      requests, successful, rejected_closed, rejected_taken, booked_slots (set)
    """
    results = {}
    booked_slots: set = set()  # "week_day_slot" keys

    for req in requests:
        week = req["week"]
        day = req["day"]
        slot = req["time_slot"]

        if week not in results:
            results[week] = {
                "requests": 0,
                "successful": 0,
                "rejected_closed": 0,
                "rejected_taken": 0,
                "booked_slots": set(),
            }

        results[week]["requests"] += 1

        # Check slot exists and is open in this schedule
        if day not in schedule_df.columns or slot not in schedule_df.index:
            results[week]["rejected_closed"] += 1
            continue

        if schedule_df.loc[slot, day] != "open":
            results[week]["rejected_closed"] += 1
            continue

        key = f"{week}_{day}_{slot}"
        if key in booked_slots:
            results[week]["rejected_taken"] += 1
            continue

        booked_slots.add(key)
        results[week]["successful"] += 1
        results[week]["booked_slots"].add(key)

    return results


def calculate_metrics(
    simulation_results: dict,
    schedule_df: pd.DataFrame,
) -> dict:
    """
    Calculates per-week metrics from simulation results:
      - idle_time_pct       : (open_slots − booked) / open_slots
      - booking_success_rate: successful / total_requests
      - slot_utilisation    : booked / open_slots
    Returns dict keyed by week number.
    """
    open_slots_per_week = int((schedule_df == "open").values.sum())
    metrics = {}

    for week, data in simulation_results.items():
        booked = len(data["booked_slots"])
        requests = data["requests"]
        successful = data["successful"]

        if open_slots_per_week > 0:
            idle_pct = (open_slots_per_week - booked) / open_slots_per_week
            utilisation = booked / open_slots_per_week
        else:
            idle_pct = 1.0
            utilisation = 0.0

        success_rate = successful / requests if requests > 0 else 0.0

        metrics[week] = {
            "idle_time_pct": round(idle_pct, 4),
            "booking_success_rate": round(success_rate, 4),
            "slot_utilisation_rate": round(utilisation, 4),
            "requests": requests,
            "successful": successful,
            "rejected": data["rejected_closed"] + data["rejected_taken"],
        }

    return metrics


def compare_models(
    df_historical: pd.DataFrame,
    fixed_schedule: pd.DataFrame,
    behaviour_schedule: pd.DataFrame,
    num_weeks: int = 6,
    seed: int = 42,
) -> tuple:
    """
    Runs the simulation for both models using the same request pool.
    Returns (avg_fixed: dict, avg_behaviour: dict, comparison_df: DataFrame).
    comparison_df has one row per week with columns for both models.
    """
    requests = generate_requests(df_historical, num_weeks, seed)

    fixed_res = run_simulation(requests, fixed_schedule)
    beh_res = run_simulation(requests, behaviour_schedule)

    fixed_m = calculate_metrics(fixed_res, fixed_schedule)
    beh_m = calculate_metrics(beh_res, behaviour_schedule)

    rows = []
    for week in range(1, num_weeks + 1):
        fm = fixed_m.get(week, {})
        bm = beh_m.get(week, {})
        rows.append({
            "Week": week,
            "Fixed - Idle Time": fm.get("idle_time_pct", 0),
            "Fixed - Success Rate": fm.get("booking_success_rate", 0),
            "Fixed - Utilisation": fm.get("slot_utilisation_rate", 0),
            "Fixed - Requests": fm.get("requests", 0),
            "Fixed - Successful": fm.get("successful", 0),
            "Fixed - Rejected": fm.get("rejected", 0),
            "Behaviour - Idle Time": bm.get("idle_time_pct", 0),
            "Behaviour - Success Rate": bm.get("booking_success_rate", 0),
            "Behaviour - Utilisation": bm.get("slot_utilisation_rate", 0),
            "Behaviour - Requests": bm.get("requests", 0),
            "Behaviour - Successful": bm.get("successful", 0),
            "Behaviour - Rejected": bm.get("rejected", 0),
        })

    comparison_df = pd.DataFrame(rows)

    def _avg(metrics_dict: dict, key: str) -> float:
        vals = [v[key] for v in metrics_dict.values() if key in v]
        return round(np.mean(vals), 4) if vals else 0.0

    avg_fixed = {
        "idle_time_pct": _avg(fixed_m, "idle_time_pct"),
        "booking_success_rate": _avg(fixed_m, "booking_success_rate"),
        "slot_utilisation_rate": _avg(fixed_m, "slot_utilisation_rate"),
        "total_requests": sum(v.get("requests", 0) for v in fixed_m.values()),
        "total_successful": sum(v.get("successful", 0) for v in fixed_m.values()),
        "total_rejected": sum(v.get("rejected", 0) for v in fixed_m.values()),
    }
    avg_behaviour = {
        "idle_time_pct": _avg(beh_m, "idle_time_pct"),
        "booking_success_rate": _avg(beh_m, "booking_success_rate"),
        "slot_utilisation_rate": _avg(beh_m, "slot_utilisation_rate"),
        "total_requests": sum(v.get("requests", 0) for v in beh_m.values()),
        "total_successful": sum(v.get("successful", 0) for v in beh_m.values()),
        "total_rejected": sum(v.get("rejected", 0) for v in beh_m.values()),
    }

    return avg_fixed, avg_behaviour, comparison_df
