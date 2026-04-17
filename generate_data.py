import pandas as pd
import numpy as np
import random
from datetime import date, timedelta
import os

# ─────────────────────────────────────────────
# SEED FOR REPRODUCIBILITY
# ─────────────────────────────────────────────
random.seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────
# 1. DATE RANGE: 2 FULL YEARS
# ─────────────────────────────────────────────
START_DATE = date(2024, 1, 1)
END_DATE   = date(2025, 12, 31)

# ─────────────────────────────────────────────
# 2. TIME SLOTS (09:00 to 20:00, hourly)
# ─────────────────────────────────────────────
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"
]

# ─────────────────────────────────────────────
# 3. MONTHLY SEASONAL MULTIPLIERS
#    December = peak (1.0), January = quietest
# ─────────────────────────────────────────────
MONTH_MULTIPLIER = {
    1: 0.55,   # January   - very quiet, post-Christmas slump
    2: 0.60,   # February  - still slow
    3: 0.70,   # March     - picking up, spring mood
    4: 0.75,   # April     - moderate, Easter boost
    5: 0.80,   # May       - steady growth
    6: 0.85,   # June      - summer start, weddings begin
    7: 0.82,   # July      - holidays reduce some weekday demand
    8: 0.78,   # August    - school holidays, mixed demand
    9: 0.84,   # September - back to routine, good demand
    10: 0.90,  # October   - building toward year end
    11: 0.94,  # November  - pre-Christmas prep starts
    12: 1.00,  # December  - peak, parties, weddings, events
}

# ─────────────────────────────────────────────
# 4. DAY OF WEEK MULTIPLIERS
#    Saturday = peak (1.0), Monday = quietest
# ─────────────────────────────────────────────
# weekday() returns: 0=Monday ... 6=Sunday
DAY_MULTIPLIER = {
    0: 0.50,   # Monday    - slowest day
    1: 0.55,   # Tuesday   - nearly as slow
    2: 0.65,   # Wednesday - mid-week pickup
    3: 0.75,   # Thursday  - noticeably busier
    4: 0.88,   # Friday    - high demand, evening bookings
    5: 1.00,   # Saturday  - peak day
    6: 0.72,   # Sunday    - busy morning, drops afternoon
}

# ─────────────────────────────────────────────
# 5. TIME SLOT DEMAND MULTIPLIERS
#    Varies by weekday vs weekend
# ─────────────────────────────────────────────
SLOT_MULTIPLIER_WEEKDAY = {
    "09:00": 0.55,  # early morning, moderate interest
    "10:00": 0.65,  # building up
    "11:00": 0.70,  # decent demand
    "12:00": 0.45,  # lunch dip starts
    "13:00": 0.38,  # lunch slump, quietest slot
    "14:00": 0.50,  # recovering
    "15:00": 0.62,  # school run time, moderate
    "16:00": 0.72,  # picking up after work
    "17:00": 0.95,  # peak after-work slot
    "18:00": 1.00,  # peak - highest demand on weekdays
    "19:00": 0.75,  # still active but declining
}

SLOT_MULTIPLIER_WEEKEND = {
    "09:00": 0.85,  # weekend mornings popular
    "10:00": 1.00,  # peak on weekend - late morning
    "11:00": 0.95,  # very busy
    "12:00": 0.80,  # good demand continues
    "13:00": 0.70,  # slight dip but still busy
    "14:00": 0.72,  # steady afternoon
    "15:00": 0.68,  # moderate
    "16:00": 0.60,  # starting to wind down
    "17:00": 0.50,  # people heading home
    "18:00": 0.40,  # quiet on weekends in evening
    "19:00": 0.30,  # minimal demand
}

# ─────────────────────────────────────────────
# 6. UK BANK HOLIDAYS (England) 2024 and 2025
# ─────────────────────────────────────────────
BANK_HOLIDAYS = {
    # 2024
    date(2024, 1, 1),   # New Year's Day
    date(2024, 3, 29),  # Good Friday
    date(2024, 4, 1),   # Easter Monday
    date(2024, 5, 6),   # Early May Bank Holiday
    date(2024, 5, 27),  # Spring Bank Holiday
    date(2024, 8, 26),  # Summer Bank Holiday
    date(2024, 12, 25), # Christmas Day
    date(2024, 12, 26), # Boxing Day
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 4, 21),  # Easter Monday
    date(2025, 5, 5),   # Early May Bank Holiday
    date(2025, 5, 26),  # Spring Bank Holiday
    date(2025, 8, 25),  # Summer Bank Holiday
    date(2025, 12, 25), # Christmas Day
    date(2025, 12, 26), # Boxing Day
}

# ─────────────────────────────────────────────
# 7. SERVICE DURATIONS (minutes) BY TIME SLOT
#    Morning = longer treatments, evenings = shorter
# ─────────────────────────────────────────────
def get_service_duration(slot, day_of_week):
    """Return realistic service duration in minutes."""
    hour = int(slot.split(":")[0])
    is_weekend = day_of_week >= 5

    if is_weekend and hour <= 12:
        # Weekend mornings: longer treatments like colour or full styling
        return random.choices(
            [30, 45, 60, 90, 120],
            weights=[10, 20, 35, 25, 10]
        )[0]
    elif hour >= 17:
        # Evening slots: quick appointments after work
        return random.choices(
            [30, 45, 60, 90],
            weights=[35, 35, 20, 10]
        )[0]
    elif 13 <= hour <= 15:
        # Lunch and early afternoon: mixed
        return random.choices(
            [30, 45, 60, 90],
            weights=[25, 30, 30, 15]
        )[0]
    else:
        # Standard morning and mid slots
        return random.choices(
            [30, 45, 60, 90, 120],
            weights=[15, 25, 35, 20, 5]
        )[0]

# ─────────────────────────────────────────────
# 8. BOOKING LEAD TIME (days in advance)
#    Weekend slots booked earlier, evening slots often same-day
# ─────────────────────────────────────────────
def get_lead_time(slot, day_of_week):
    """Return how many days in advance the booking was made."""
    hour = int(slot.split(":")[0])
    is_weekend = day_of_week >= 5

    if is_weekend:
        # Weekend slots booked well in advance
        return random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7, 10, 14],
            weights=[3, 5, 10, 15, 18, 15, 12, 10, 7, 5]
        )[0]
    elif hour >= 17:
        # Evening weekday slots - often same day or day before
        return random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7],
            weights=[20, 25, 20, 15, 10, 5, 3, 2]
        )[0]
    else:
        # Standard weekday slots - moderate lead time
        return random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7, 10],
            weights=[8, 15, 18, 18, 15, 10, 7, 5, 4]
        )[0]

# ─────────────────────────────────────────────
# 9. CANCELLATION PROBABILITY
#    Higher for late slots, quiet months, short lead time
# ─────────────────────────────────────────────
def get_cancellation_prob(slot, day_of_week, month, lead_time):
    """Return probability of cancellation between 0 and 1."""
    hour = int(slot.split(":")[0])
    base = 0.12  # baseline 12% cancellation

    # Late evening slots cancel more
    if hour >= 19:
        base += 0.10
    elif hour >= 17:
        base += 0.04

    # Quiet months cancel more
    if month in [1, 2]:
        base += 0.08
    elif month in [7, 8]:
        base += 0.04

    # Monday and Tuesday cancel more
    if day_of_week in [0, 1]:
        base += 0.06

    # Same day or next day bookings cancel more
    if lead_time == 0:
        base += 0.12
    elif lead_time == 1:
        base += 0.06

    return min(base, 0.55)  # cap at 55%

# ─────────────────────────────────────────────
# 10. NO-SHOW PROBABILITY (separate from cancellation)
#     No-show = did not come, gave no warning
# ─────────────────────────────────────────────
def get_noshow_prob(slot, lead_time, is_repeat):
    """Return probability of no-show between 0 and 1."""
    hour = int(slot.split(":")[0])
    base = 0.05  # baseline 5%

    if hour >= 19:
        base += 0.06
    if lead_time == 0:
        base += 0.08
    if not is_repeat:
        base += 0.04  # new customers no-show more

    return min(base, 0.30)

# ─────────────────────────────────────────────
# 11. CUSTOMER POOL
#     Mix of repeat customers (loyal) and new customers
# ─────────────────────────────────────────────
NUM_REPEAT_CUSTOMERS = 80    # loyal regulars
NUM_NEW_CUSTOMERS    = 400   # occasional or one-off visitors

repeat_customers = [f"RC{str(i).zfill(4)}" for i in range(1, NUM_REPEAT_CUSTOMERS + 1)]
new_customers    = [f"NC{str(i).zfill(4)}" for i in range(1, NUM_NEW_CUSTOMERS + 1)]

# Assign preferred day and slot to each repeat customer
# This simulates loyal customers always booking the same time
repeat_customer_preferences = {}
for cid in repeat_customers:
    preferred_day  = random.choice([0, 1, 2, 3, 4, 5, 6])
    preferred_slot = random.choice(TIME_SLOTS)
    repeat_customer_preferences[cid] = {
        "day":  preferred_day,
        "slot": preferred_slot
    }

# ─────────────────────────────────────────────
# 12. MAIN DATA GENERATION LOOP
# ─────────────────────────────────────────────
records = []
booking_id = 1

current_date = START_DATE
while current_date <= END_DATE:

    day_of_week  = current_date.weekday()   # 0=Mon, 6=Sun
    month        = current_date.month
    year         = current_date.year
    is_holiday   = current_date in BANK_HOLIDAYS
    is_weekend   = day_of_week >= 5

    # Bank holidays treated like Saturdays for demand
    effective_day = 5 if is_holiday else day_of_week

    month_mult = MONTH_MULTIPLIER[month]
    day_mult   = DAY_MULTIPLIER[effective_day]

    # Year 2 gets small random variation (+/- 5%) for realism
    year_noise = 1.0 if year == 2024 else random.uniform(0.95, 1.05)

    for slot in TIME_SLOTS:

        # Choose correct slot multiplier based on day type
        if effective_day >= 5:
            slot_mult = SLOT_MULTIPLIER_WEEKEND[slot]
        else:
            slot_mult = SLOT_MULTIPLIER_WEEKDAY[slot]

        # Combined demand probability for this specific slot
        demand_prob = month_mult * day_mult * slot_mult * year_noise

        # Each slot can hold 1 to 3 bookings depending on duration
        # Higher demand probability = more likely to be fully booked
        max_bookings = 2 if demand_prob > 0.7 else 1

        for _ in range(max_bookings):

            # Roll the dice - does a booking happen here?
            if random.random() > demand_prob:
                continue  # no booking in this slot this pass

            # ── Determine customer type ──────────────────────
            # 60% repeat, 40% new (realistic for small service business)
            if random.random() < 0.60:
                is_repeat   = True
                customer_id = random.choice(repeat_customers)
                # Repeat customers sometimes deviate from preference
                pref = repeat_customer_preferences[customer_id]
                if random.random() < 0.75:
                    # Stick to their preferred slot
                    if pref["day"] != day_of_week:
                        continue  # they would not book on this day
                    booking_slot = pref["slot"]
                    if booking_slot != slot:
                        continue  # they would not book this slot
                else:
                    booking_slot = slot  # occasional deviation
            else:
                is_repeat   = False
                customer_id = random.choice(new_customers)
                booking_slot = slot

            # ── Lead time ───────────────────────────────────
            lead_time = get_lead_time(booking_slot, day_of_week)

            # ── Service duration ─────────────────────────────
            duration = get_service_duration(booking_slot, day_of_week)

            # ── Cancellation ─────────────────────────────────
            cancel_prob  = get_cancellation_prob(booking_slot, day_of_week, month, lead_time)
            is_cancelled = 1 if random.random() < cancel_prob else 0

            # ── No-show (only if not cancelled) ──────────────
            if is_cancelled:
                is_noshow = 0
            else:
                noshow_prob = get_noshow_prob(booking_slot, lead_time, is_repeat)
                is_noshow   = 1 if random.random() < noshow_prob else 0

            # ── Season label ─────────────────────────────────
            if month in [12, 1, 2]:
                season = "Winter"
            elif month in [3, 4, 5]:
                season = "Spring"
            elif month in [6, 7, 8]:
                season = "Summer"
            else:
                season = "Autumn"

            # ── Build record ──────────────────────────────────
            records.append({
                "booking_id":       f"BK{str(booking_id).zfill(5)}",
                "date":             current_date.strftime("%Y-%m-%d"),
                "year":             year,
                "month":            month,
                "month_name":       current_date.strftime("%B"),
                "season":           season,
                "day_of_week":      day_of_week,
                "day_name":         current_date.strftime("%A"),
                "is_weekend":       int(is_weekend),
                "is_public_holiday":int(is_holiday),
                "time_slot":        booking_slot,
                "slot_hour":        int(booking_slot.split(":")[0]),
                "service_duration_mins": duration,
                "lead_time_days":   lead_time,
                "customer_id":      customer_id,
                "is_repeat_customer": int(is_repeat),
                "is_cancelled":     is_cancelled,
                "is_noshow":        is_noshow,
                "attended":         int(not is_cancelled and not is_noshow),
            })

            booking_id += 1

    current_date += timedelta(days=1)

# ─────────────────────────────────────────────
# 13. SAVE TO CSV
# ─────────────────────────────────────────────
df = pd.DataFrame(records)

# Sort by date and slot for clean ordering
df = df.sort_values(["date", "time_slot"]).reset_index(drop=True)

output_path = "/home/claude/scheduling_project/booking_data.csv"
df.to_csv(output_path, index=False)

# ─────────────────────────────────────────────
# 14. SUMMARY REPORT
# ─────────────────────────────────────────────
print("=" * 55)
print("  SYNTHETIC BOOKING DATA GENERATION COMPLETE")
print("=" * 55)
print(f"\n  Total records generated : {len(df):,}")
print(f"  Date range              : {df['date'].min()} to {df['date'].max()}")
print(f"  Unique customers        : {df['customer_id'].nunique():,}")
print(f"  Repeat customers        : {df[df['is_repeat_customer']==1]['customer_id'].nunique():,}")
print(f"  New customers           : {df[df['is_repeat_customer']==0]['customer_id'].nunique():,}")
print(f"\n  Cancellation rate       : {df['is_cancelled'].mean()*100:.1f}%")
print(f"  No-show rate            : {df['is_noshow'].mean()*100:.1f}%")
print(f"  Attendance rate         : {df['attended'].mean()*100:.1f}%")

print(f"\n  Bookings by year:")
for yr, grp in df.groupby("year"):
    print(f"    {yr} : {len(grp):,} bookings")

print(f"\n  Busiest months (top 5):")
month_counts = df.groupby("month_name").size().sort_values(ascending=False).head(5)
for mth, cnt in month_counts.items():
    print(f"    {mth:<12}: {cnt:,}")

print(f"\n  Busiest days:")
day_counts = df.groupby("day_name").size().sort_values(ascending=False)
for day, cnt in day_counts.items():
    print(f"    {day:<12}: {cnt:,}")

print(f"\n  Busiest time slots:")
slot_counts = df.groupby("time_slot").size().sort_values(ascending=False)
for slot, cnt in slot_counts.items():
    print(f"    {slot} : {cnt:,}")

print(f"\n  File saved to: {output_path}")
print("=" * 55)
