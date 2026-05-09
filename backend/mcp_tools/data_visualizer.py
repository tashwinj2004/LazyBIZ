from __future__ import annotations
"""
MCP Tool — Data Visualizer
Generates 6 chart types using Matplotlib / Seaborn.
Returns each chart as a Base64-encoded PNG string.
"""
import io
import base64
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (no display needed)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Global style ────────────────────────────────────────────
DARK_BG   = "#ffffff"
CARD_BG   = "#ffffff"
GRID_CLR  = "#eaecf0"
TEXT_CLR  = "#101828"
MUTED_CLR = "#667085"
CYAN      = "#0284c7"
EMERALD   = "#059669"
INDIGO    = "#4f46e5"
WARN      = "#f59e0b"
ERROR     = "#dc2626"

PALETTE = [CYAN, EMERALD, INDIGO, WARN, ERROR,
           "#a78bfa", "#fb923c", "#f472b6", "#34d399", "#60a5fa"]

def _style_ax(ax, fig):
    """Apply dark theme to an axes."""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=MUTED_CLR, labelsize=9)
    ax.xaxis.label.set_color(MUTED_CLR)
    ax.yaxis.label.set_color(MUTED_CLR)
    ax.title.set_color(TEXT_CLR)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.grid(color=GRID_CLR, linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)


def _to_base64(fig) -> str:
    """Convert a matplotlib figure to a base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def _detect_col(df, keywords, dtypes=None):
    """Find the first column matching keywords (and optionally dtype)."""
    for c in df.columns:
        if dtypes and not pd.api.types.is_dtype_equal(df[c].dtype, dtypes) and \
                not any(pd.api.types.is_dtype_equal(df[c].dtype, d) for d in dtypes):
            continue
        if any(k in c.lower() for k in keywords):
            return c
    return None


# ────────────────────────────────────────────────────────────
# INDIVIDUAL CHART FUNCTIONS
# ────────────────────────────────────────────────────────────

def chart_revenue_trend(df: pd.DataFrame, rev_col: str, date_col: str | None) -> dict:
    """Line chart: revenue/sales over time."""
    fig, ax = plt.subplots(figsize=(9, 4))
    _style_ax(ax, fig)

    if date_col and date_col in df.columns:
        temp = df[[date_col, rev_col]].copy()
        # Only convert if not already datetime
        if not pd.api.types.is_datetime64_any_dtype(temp[date_col]):
            temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col, rev_col])
        monthly = temp.groupby(temp[date_col].dt.to_period('M'))[rev_col].sum()
        monthly = monthly.sort_index()
        x = [d.to_timestamp().strftime("%b '%y") for d in monthly.index]
        y = monthly.values
    else:
        y = df[rev_col].dropna().values[:24]
        x = [f"#{i+1}" for i in range(len(y))]

    ax.plot(x, y, color=CYAN, linewidth=2.5, marker="o",
            markersize=5, markerfacecolor=CYAN, markeredgecolor=DARK_BG,
            markeredgewidth=2, zorder=3)
    ax.fill_between(range(len(x)), y, alpha=0.12, color=CYAN)
    ax.set_xticks(range(len(x)))
    ax.set_xticklabels(x, rotation=35, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K" if v >= 1e3 else f"${v:.0f}"
    ))
    ax.set_title("Revenue Trend Over Time", fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    return {"id": "revenue_trend", "title": "Revenue Trend", "image": _to_base64(fig)}


def chart_top_categories(df: pd.DataFrame, cat_col: str, rev_col: str, n=8) -> dict:
    """Horizontal bar chart: top N categories by revenue."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _style_ax(ax, fig)

    grouped = df.groupby(cat_col)[rev_col].sum().nlargest(n).sort_values()
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(grouped))]
    bars = ax.barh(grouped.index.astype(str), grouped.values,
                   color=colors, height=0.6, edgecolor="none")

    for bar, val in zip(bars, grouped.values):
        label = f"${val/1e6:.1f}M" if val >= 1e6 else f"${val/1e3:.1f}K" if val >= 1e3 else f"${val:.0f}"
        ax.text(bar.get_width() + grouped.values.max() * 0.01,
                bar.get_y() + bar.get_height() / 2,
                label, va="center", ha="left", color=TEXT_CLR, fontsize=9)

    ax.set_xlabel("Total Revenue", color=MUTED_CLR)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"
    ))
    ax.set_title(f"Top {n} by '{cat_col}'", fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    return {"id": "top_categories", "title": f"Top {n} Categories", "image": _to_base64(fig)}


def chart_sentiment(df: pd.DataFrame, sent_col: str) -> dict:
    """Donut chart: sentiment distribution."""
    def _score(text):
        if not isinstance(text, str):
            return "neutral"
        t = text.lower()
        pos = sum(1 for w in ["great","excellent","good","love","best","perfect","awesome"] if w in t)
        neg = sum(1 for w in ["bad","terrible","worst","hate","awful","poor","horrible","broken"] if w in t)
        return "positive" if pos > neg else "negative" if neg > pos else "neutral"

    sentiments = df[sent_col].dropna().astype(str).apply(_score)
    counts = sentiments.value_counts()
    labels = [l.capitalize() for l in counts.index]
    sizes  = counts.values
    colors_map = {"positive": EMERALD, "neutral": CYAN, "negative": ERROR}
    clrs   = [colors_map.get(l.lower(), INDIGO) for l in counts.index]

    fig, ax = plt.subplots(figsize=(6, 5))
    fig.patch.set_facecolor(DARK_BG)
    wedges, _, autotexts = ax.pie(
        sizes, labels=labels, colors=clrs, autopct="%1.1f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops={"edgecolor": DARK_BG, "linewidth": 3, "width": 0.55}
    )
    for at in autotexts:
        at.set_color(DARK_BG)
        at.set_fontsize(9)
        at.set_fontweight("bold")
    for t in ax.texts:
        t.set_color(TEXT_CLR)
        t.set_fontsize(10)
    ax.set_title("Sentiment Distribution", fontsize=13, fontweight="bold", color=TEXT_CLR, pad=14)
    fig.tight_layout()
    return {"id": "sentiment", "title": "Sentiment Distribution", "image": _to_base64(fig)}


def chart_correlation_heatmap(df: pd.DataFrame) -> dict:
    """Heatmap: Pearson correlation between numeric columns."""
    numeric = df.select_dtypes(include=[np.number])
    corr = numeric.corr()

    fig, ax = plt.subplots(figsize=(max(6, len(corr.columns) * 0.9 + 2),
                                    max(5, len(corr.columns) * 0.9 + 1)))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(CARD_BG)

    cmap = sns.diverging_palette(195, 340, s=80, l=40, as_cmap=True)
    sns.heatmap(corr, ax=ax, cmap=cmap, center=0, vmin=-1, vmax=1,
                annot=True, fmt=".2f", annot_kws={"size": 9, "color": TEXT_CLR},
                linewidths=0.5, linecolor=DARK_BG,
                cbar_kws={"shrink": 0.8})

    ax.tick_params(colors=MUTED_CLR, labelsize=9)
    ax.set_title("Feature Correlation Heatmap", fontsize=13, fontweight="bold",
                 color=TEXT_CLR, pad=14)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(TEXT_CLR)
    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(colors=MUTED_CLR, labelsize=8)
    fig.tight_layout()
    return {"id": "correlation", "title": "Correlation Heatmap", "image": _to_base64(fig)}


def chart_distribution(df: pd.DataFrame, rev_col: str) -> dict:
    """Histogram + KDE: value distribution."""
    fig, ax = plt.subplots(figsize=(8, 4))
    _style_ax(ax, fig)

    data = df[rev_col].dropna()
    ax.hist(data, bins=30, color=CYAN, alpha=0.35, edgecolor=CARD_BG, linewidth=0.5)

    # KDE overlay
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(data)
        xs = np.linspace(data.min(), data.max(), 300)
        ys = kde(xs)
        # Scale KDE to histogram height
        hist_vals, bin_edges = np.histogram(data, bins=30)
        bin_width = bin_edges[1] - bin_edges[0]
        scale = hist_vals.max() / ys.max()
        ax.plot(xs, ys * scale, color=EMERALD, linewidth=2.5)
    except Exception:
        pass

    ax.set_xlabel(rev_col, color=MUTED_CLR)
    ax.set_ylabel("Frequency", color=MUTED_CLR)
    ax.set_title(f"Distribution of '{rev_col}'", fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    return {"id": "distribution", "title": "Value Distribution", "image": _to_base64(fig)}


def chart_monthly_comparison(df: pd.DataFrame, rev_col: str, date_col: str) -> dict:
    """Grouped bar chart: month-over-month comparison (last 2 years)."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    _style_ax(ax, fig)

    temp = df[[date_col, rev_col]].copy()
    if not pd.api.types.is_datetime64_any_dtype(temp[date_col]):
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
    temp = temp.dropna(subset=[date_col, rev_col])
    
    # Robust aggregation
    monthly = temp.groupby(temp[date_col].dt.to_period('M'))[rev_col].sum()
    monthly = monthly.sort_index()

    if monthly.empty:
        raise ValueError("No data available for month-over-month comparison.")

    # Convert to DataFrame for easier pivot operations
    monthly_df = monthly.reset_index()
    monthly_df["year"] = monthly_df[date_col].dt.year
    monthly_df["month"] = monthly_df[date_col].dt.month

    pivot = monthly_df.pivot_table(index="month", columns="year", values=rev_col, aggfunc="sum")
    pivot = pivot[sorted(pivot.columns)[-2:]]      # last 2 years only

    x = np.arange(12)
    width = 0.38
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    cols = list(pivot.columns)
    clrs = [CYAN, EMERALD]

    for i, (yr, clr) in enumerate(zip(cols, clrs)):
        vals = [pivot.loc[m, yr] if m in pivot.index else 0 for m in range(1, 13)]
        ax.bar(x + (i - 0.5) * width, vals, width, label=str(yr), color=clr, alpha=0.85, edgecolor="none")

    ax.set_xticks(x)
    ax.set_xticklabels(month_labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"
    ))
    ax.legend(facecolor=CARD_BG, edgecolor=GRID_CLR, labelcolor=TEXT_CLR, fontsize=9)
    ax.set_title("Month-over-Month Comparison", fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    return {"id": "monthly_comparison", "title": "Month-over-Month", "image": _to_base64(fig)}


# ────────────────────────────────────────────────────────────
# MAIN TOOL ENTRY POINT
# ────────────────────────────────────────────────────────────

def visualize_data(df: pd.DataFrame, analysis: dict) -> dict:
    print("[LazyBIZ] Visualization Engine: VERIFIED FIXED (No 'charts' variable)")
    result = {
        "tool": "data_visualizer",
        "timestamp": datetime.utcnow().isoformat(),
        "charts": [],
        "chart_count": 0
    }

    kpis      = analysis.get("kpis", {})
    trend     = analysis.get("trend", {})
    sent      = analysis.get("sentiment", {})
    perf      = analysis.get("performers", {})
    numeric   = df.select_dtypes(include=[np.number])

    rev_col  = kpis.get("revenue_column")
    date_col = trend.get("date_column")
    cat_col  = perf.get("category_column")
    sent_col = sent.get("column")

    # Chart 1: Revenue Trend
    if rev_col:
        try:
            result["charts"].append(chart_revenue_trend(df, rev_col, date_col))
        except Exception as e:
            result["charts"].append({"id": "revenue_trend", "title": "Revenue Trend", "error": str(e)})

    # Chart 2: Top Categories
    if cat_col and rev_col:
        try:
            result["charts"].append(chart_top_categories(df, cat_col, rev_col))
        except Exception as e:
            result["charts"].append({"id": "top_categories", "title": "Top Categories", "error": str(e)})

    # Chart 3: Sentiment donut
    if sent_col:
        try:
            result["charts"].append(chart_sentiment(df, sent_col))
        except Exception as e:
            result["charts"].append({"id": "sentiment", "title": "Sentiment", "error": str(e)})

    # Chart 4: Correlation Heatmap
    if len(numeric.columns) >= 2:
        try:
            result["charts"].append(chart_correlation_heatmap(df))
        except Exception as e:
            result["charts"].append({"id": "correlation", "title": "Correlation", "error": str(e)})

    # Chart 5: Distribution
    if rev_col:
        try:
            result["charts"].append(chart_distribution(df, rev_col))
        except Exception as e:
            result["charts"].append({"id": "distribution", "title": "Distribution", "error": str(e)})

    # Chart 6: Monthly Comparison
    if rev_col and date_col:
        try:
            result["charts"].append(chart_monthly_comparison(df, rev_col, date_col))
        except Exception as e:
            result["charts"].append({"id": "monthly_comparison", "title": "Monthly Comparison", "error": str(e)})

    result["chart_count"] = len([c for c in result["charts"] if "image" in c])
    return result
