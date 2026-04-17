"""
utils/charts.py
All Plotly chart and HTML grid functions used across pages.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

COLORS = {
    "green": "#2E7D32",
    "amber": "#F57C00",
    "red": "#C62828",
    "grey": "#757575",
    "light_green": "#C8E6C9",
    "light_amber": "#FFE0B2",
    "blue": "#1565C0",
    "bg": "#FAFAFA",
}


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

def plot_demand_heatmap(
    freq_pivot: pd.DataFrame,
    cancel_pivot: pd.DataFrame = None,
    leadtime_pivot: pd.DataFrame = None,
) -> go.Figure:
    """Returns an interactive Plotly heatmap of booking frequency (green scale)."""
    if freq_pivot.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available for selected month",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    days = [d for d in DAY_ORDER if d in freq_pivot.columns]
    slots = sorted(freq_pivot.index.tolist())

    z = freq_pivot.reindex(index=slots, columns=days).fillna(0).values

    hover_text = []
    for slot in slots:
        row_hover = []
        for day in days:
            count = freq_pivot.loc[slot, day] if (slot in freq_pivot.index and day in freq_pivot.columns) else 0
            cancel = (cancel_pivot.loc[slot, day]
                      if (cancel_pivot is not None and slot in cancel_pivot.index and day in cancel_pivot.columns)
                      else 0)
            lead = (leadtime_pivot.loc[slot, day]
                    if (leadtime_pivot is not None and slot in leadtime_pivot.index and day in leadtime_pivot.columns)
                    else 0)
            row_hover.append(
                f"<b>{day} @ {slot}</b><br>"
                f"Bookings: {count:.1f}<br>"
                f"Cancel Rate: {cancel * 100:.1f}%<br>"
                f"Avg Lead Time: {lead:.1f} days"
            )
        hover_text.append(row_hover)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=days,
        y=slots,
        colorscale="Greens",
        hoverinfo="text",
        text=hover_text,
        colorbar=dict(title="Weighted<br>Bookings"),
    ))
    fig.update_layout(
        title="Booking Demand Heatmap — Same-Period Historical Data",
        xaxis_title="Day of Week",
        yaxis_title="Time Slot",
        yaxis=dict(autorange="reversed"),
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=40, t=60, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# Bar charts
# ---------------------------------------------------------------------------

def plot_day_bar_chart(df: pd.DataFrame) -> go.Figure:
    """Returns a Plotly bar chart of booking volume by day of week."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    day_counts = df.groupby("day_name").size().reset_index(name="bookings")
    day_counts["day_name"] = pd.Categorical(day_counts["day_name"], categories=DAY_ORDER, ordered=True)
    day_counts = day_counts.sort_values("day_name")

    fig = px.bar(
        day_counts, x="day_name", y="bookings",
        title="Booking Volume by Day of Week (Selected Month)",
        labels={"day_name": "Day", "bookings": "Number of Bookings"},
        color="bookings", color_continuous_scale="Greens",
    )
    fig.update_layout(
        showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
        coloraxis_showscale=False,
        xaxis_title="Day of Week", yaxis_title="Number of Bookings",
        margin=dict(t=50, b=40),
    )
    return fig


def plot_year_comparison(df: pd.DataFrame) -> go.Figure:
    """Returns a Plotly line chart comparing booking volumes across years for the selected month."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    years = sorted(df["year"].unique())
    palette = [COLORS["green"], COLORS["amber"], COLORS["blue"], COLORS["red"]]
    fig = go.Figure()

    for i, year in enumerate(years):
        year_df = df[df["year"] == year]
        day_counts = year_df.groupby("day_name").size().reset_index(name="bookings")
        day_counts["day_name"] = pd.Categorical(day_counts["day_name"], categories=DAY_ORDER, ordered=True)
        day_counts = day_counts.sort_values("day_name")

        fig.add_trace(go.Scatter(
            x=day_counts["day_name"],
            y=day_counts["bookings"],
            mode="lines+markers",
            name=str(year),
            line=dict(color=palette[i % len(palette)], width=2),
            marker=dict(size=8),
        ))

    fig.update_layout(
        title="Year-over-Year Comparison (Selected Month)",
        xaxis_title="Day of Week",
        yaxis_title="Number of Bookings",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title="Year",
    )
    return fig


# ---------------------------------------------------------------------------
# Schedule grid (HTML)
# ---------------------------------------------------------------------------

def plot_schedule_grid(schedule_df: pd.DataFrame, holiday_info: dict = None) -> str:
    """
    Returns an HTML table with colour-coded cells for st.markdown.
    Status values: 'open' | 'marginal' | 'closed' | 'buffered'
    """
    if schedule_df.empty:
        return "<p style='color:#757575;'>No schedule generated yet.</p>"

    holiday_info = holiday_info or {}
    days = [d for d in DAY_ORDER if d in schedule_df.columns]
    slots = list(schedule_df.index)

    css = """
    <style>
    .sched-wrap{overflow-x:auto;}
    .sched-tbl{border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:12px;min-width:600px;}
    .sched-tbl th{background:#1B5E20;color:#fff;padding:8px 6px;text-align:center;font-weight:bold;white-space:nowrap;}
    .sched-tbl td{padding:5px 4px;text-align:center;border:1px solid #E0E0E0;white-space:nowrap;}
    .s-lbl{background:#E8F5E9;font-weight:bold;color:#2E7D32;}
    .s-open{background:#C8E6C9;color:#1B5E20;font-weight:bold;}
    .s-marginal{background:#FFE0B2;color:#E65100;font-weight:bold;}
    .s-closed{background:#F5F5F5;color:#9E9E9E;}
    .s-buffered{background:#BBDEFB;color:#0D47A1;}
    .s-holiday{background:#FFCDD2;color:#B71C1C;font-weight:bold;}
    </style>
    """

    html = css + "<div class='sched-wrap'><table class='sched-tbl'><thead><tr><th>Time</th>"
    for day in days:
        label = day[:3]
        if day in holiday_info:
            label += f"<br><small style='font-weight:normal;'>🏖 {holiday_info[day]}</small>"
        html += f"<th>{label}</th>"
    html += "</tr></thead><tbody>"

    for slot in slots:
        html += f"<tr><td class='s-lbl'>{slot}</td>"
        for day in days:
            status = schedule_df.loc[slot, day] if day in schedule_df.columns else "closed"
            is_holiday = day in holiday_info

            if is_holiday and status != "closed":
                css_cls, symbol, lbl = "s-holiday", "★", "Holiday"
            elif status == "open":
                css_cls, symbol, lbl = "s-open", "✓", "Open"
            elif status == "marginal":
                css_cls, symbol, lbl = "s-marginal", "⚠", "Marginal"
            elif status == "buffered":
                css_cls, symbol, lbl = "s-buffered", "◈", "Buffer"
            else:
                css_cls, symbol, lbl = "s-closed", "✗", "Closed"

            html += f"<td class='{css_cls}'>{symbol} {lbl}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# ---------------------------------------------------------------------------
# Metric comparison
# ---------------------------------------------------------------------------

def plot_metric_comparison(fixed_metrics: dict, behaviour_metrics: dict) -> go.Figure:
    """Returns a grouped Plotly bar chart comparing model metrics."""
    metric_labels = ["Idle Time %", "Booking Success Rate %", "Slot Utilisation %"]
    fixed_vals = [
        fixed_metrics.get("idle_time_pct", 0) * 100,
        fixed_metrics.get("booking_success_rate", 0) * 100,
        fixed_metrics.get("slot_utilisation_rate", 0) * 100,
    ]
    beh_vals = [
        behaviour_metrics.get("idle_time_pct", 0) * 100,
        behaviour_metrics.get("booking_success_rate", 0) * 100,
        behaviour_metrics.get("slot_utilisation_rate", 0) * 100,
    ]

    fig = go.Figure(data=[
        go.Bar(name="Fixed Schedule", x=metric_labels, y=fixed_vals,
               marker_color=COLORS["grey"],
               text=[f"{v:.1f}%" for v in fixed_vals], textposition="outside"),
        go.Bar(name="Behaviour-Based", x=metric_labels, y=beh_vals,
               marker_color=COLORS["green"],
               text=[f"{v:.1f}%" for v in beh_vals], textposition="outside"),
    ])
    fig.update_layout(
        barmode="group",
        title="Performance Metrics: Fixed vs Behaviour-Based Schedule",
        yaxis=dict(title="Percentage (%)", range=[0, 120]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title="Model",
    )
    return fig


# ---------------------------------------------------------------------------
# Simulation line chart
# ---------------------------------------------------------------------------

def plot_simulation_lines(comparison_df: pd.DataFrame) -> go.Figure:
    """Returns a Plotly line chart of booking success rate over simulation weeks."""
    if comparison_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Run simulation to see results",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=comparison_df["Week"],
        y=comparison_df["Fixed - Success Rate"] * 100,
        mode="lines+markers",
        name="Fixed Schedule",
        line=dict(color=COLORS["grey"], width=2, dash="dot"),
        marker=dict(size=8, symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=comparison_df["Week"],
        y=comparison_df["Behaviour - Success Rate"] * 100,
        mode="lines+markers",
        name="Behaviour-Based",
        line=dict(color=COLORS["green"], width=2),
        marker=dict(size=8, symbol="diamond"),
    ))
    fig.update_layout(
        title="Booking Success Rate by Simulation Week",
        xaxis_title="Simulation Week",
        yaxis=dict(title="Booking Success Rate (%)", range=[0, 110]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title="Model",
    )
    return fig


# ---------------------------------------------------------------------------
# Monthly improvement
# ---------------------------------------------------------------------------

def plot_monthly_improvement(df: pd.DataFrame) -> go.Figure:
    """Bar chart showing estimated schedule improvement potential by month."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    month_abbr = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                  7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

    monthly = df.groupby("month").agg(
        avg_attendance=("attended", "mean"),
        cancel_rate=("is_cancelled", "mean"),
        total_bookings=("booking_id", "count"),
    ).reset_index()
    monthly["month_label"] = monthly["month"].map(month_abbr)
    # Higher attendance + lower cancellation = higher improvement potential
    monthly["improvement"] = (monthly["avg_attendance"] - monthly["cancel_rate"]) * 100

    fig = px.bar(
        monthly, x="month_label", y="improvement",
        title="Estimated Improvement Potential by Month (Attendance Rate − Cancellation Rate)",
        labels={"month_label": "Month", "improvement": "Improvement Potential (%)"},
        color="improvement", color_continuous_scale="RdYlGn",
    )
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False, coloraxis_showscale=False,
        xaxis_title="Month", yaxis_title="Improvement Potential (%)",
    )
    return fig


# ---------------------------------------------------------------------------
# Diversity bar chart
# ---------------------------------------------------------------------------

def plot_diversity_bar(diversity_pivot: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of average customer diversity score per time slot."""
    if diversity_pivot.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    avg_div = diversity_pivot.mean(axis=1).reset_index()
    avg_div.columns = ["time_slot", "avg_diversity"]
    avg_div = avg_div.sort_values("avg_diversity")

    bar_colors = [
        COLORS["green"] if v > 0.65 else (COLORS["amber"] if v >= 0.40 else COLORS["red"])
        for v in avg_div["avg_diversity"]
    ]

    fig = go.Figure(go.Bar(
        x=avg_div["avg_diversity"],
        y=avg_div["time_slot"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.2f}" for v in avg_div["avg_diversity"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Customer Diversity Score by Time Slot (avg across days)",
        xaxis=dict(title="Diversity Score (Unique Customers ÷ Total Bookings)", range=[0, 1.25]),
        yaxis_title="Time Slot",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=400,
    )
    return fig


# ---------------------------------------------------------------------------
# Cancellation table helper
# ---------------------------------------------------------------------------

def build_cancellation_table(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a cancellation-rate summary table sorted highest → lowest."""
    if df.empty:
        return pd.DataFrame()

    tbl = df.groupby("time_slot").agg(
        Total_Bookings=("booking_id", "count"),
        Cancellations=("is_cancelled", "sum"),
        Cancel_Rate=("is_cancelled", "mean"),
    ).reset_index()
    tbl["Cancel_Rate_%"] = (tbl["Cancel_Rate"] * 100).round(1)
    tbl = tbl.sort_values("Cancel_Rate_%", ascending=False)
    tbl = tbl.rename(columns={"time_slot": "Time Slot",
                               "Total_Bookings": "Total Bookings",
                               "Cancellations": "Cancellations"})
    return tbl[["Time Slot", "Total Bookings", "Cancellations", "Cancel_Rate_%"]]
