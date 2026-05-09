from __future__ import annotations
"""
MCP Tool — Data Cleaner
Handles: null imputation, duplicate removal, dtype coercion, outlier capping,
         smart date parsing (DD-MM-YYYY, YYYY-MM-DD, MM-DD-YYYY, integer DDMMYYYY,
         year/month/day integer columns, mixed formats, etc.),
         negative value removal for revenue columns,
         currency symbol stripping (incl. ₹, ₩, ₺, ₽ and all majors).
Returns a cleaned DataFrame + a cleaning report dict.
"""
import re
import pandas as pd
import numpy as np
from datetime import datetime


# ── Currency symbols to strip ─────────────────────────────────────────────
_CURRENCY_RE = r"[\$,€£¥₹₩₺₽%]"

# ── Keywords that mark a column as a date column ──────────────────────────
_DATE_KEYWORDS = ["date", "time", "period", "created", "updated", "timestamp"]

# ── Keywords that mark a column as revenue/price (never negative) ─────────
_REVENUE_KEYWORDS = [
    "revenue", "sales", "amount", "price", "cost", "income",
    "profit", "earning", "receipt", "value", "total"
]

# ── Keywords that mark a column as product/item (skip numeric coercion) ──
_PRODUCT_KEYWORDS = ["product", "item", "sku", "article", "model", "desc", "title", "name"]


# ─────────────────────────────────────────────────────────────────────────────
# DATE FORMAT DETECTION & SMART PARSING
# ─────────────────────────────────────────────────────────────────────────────

def _detect_separator_format(series: pd.Series):
    """
    Inspect a date string series and determine whether it is:
      - 'dayfirst'   → DD-MM-YYYY or DD/MM/YYYY  (day is first part)
      - 'monthfirst' → MM-DD-YYYY or MM/DD/YYYY  (month is first part)
      - 'yearfirst'  → YYYY-MM-DD or YYYY/MM/DD  (year is first part)
      - None         → cannot determine

    Strategy: Find unambiguous rows where the first or second numeric
    component exceeds 12 (can't be a month) to pin the format.
    """
    sample = series.dropna().astype(str).str.strip().head(200)

    for sep in ["-", "/", ".", " "]:
        if sample.str.contains(re.escape(sep), regex=False).mean() < 0.5:
            continue

        parts = sample.str.split(re.escape(sep), n=2, expand=True)
        if parts.shape[1] < 3:
            continue

        p0 = pd.to_numeric(parts[0], errors="coerce")
        p1 = pd.to_numeric(parts[1], errors="coerce")
        p2 = pd.to_numeric(parts[2], errors="coerce")

        # Identify which part is the year (4 digits / ≥ 1900)
        year_last  = (p2 >= 1900).mean() > 0.5   # DD-MM-YYYY or MM-DD-YYYY
        year_first = (p0 >= 1900).mean() > 0.5   # YYYY-MM-DD

        if year_first:
            return "yearfirst"

        if year_last:
            p0_gt12 = (p0 > 12).any()   # If first part ever > 12 → must be day
            p1_gt12 = (p1 > 12).any()   # If second part ever > 12 → must be day

            if p0_gt12 and not p1_gt12:
                return "dayfirst"     # DD-MM-YYYY
            if p1_gt12 and not p0_gt12:
                return "monthfirst"   # MM-DD-YYYY
            # Both ambiguous (all days ≤ 12): default to dayfirst
            # (more common internationally; also avoids the MM-DD swapping trap)
            return "dayfirst"

    return None


def _smart_parse_date(series: pd.Series) -> pd.Series | None:
    """
    Parse a date Series using automatic format detection.

    Works for:
      - YYYY-MM-DD / ISO 8601
      - DD-MM-YYYY / DD/MM/YYYY  (most of the world outside USA)
      - MM-DD-YYYY / MM/DD/YYYY  (USA format)
      - Integer-packed  DDMMYYYY (e.g. 1012024 → Jan 1, 2024)
      - Mixed-format fallback

    Returns a parsed Series if ≥ 50 % of values succeed, else None.
    """
    THRESHOLD = 0.5
    n = max(len(series), 1)

    # Already datetime → return as-is
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    # Detect separator-based format first  ──────────────────────────────────
    fmt = _detect_separator_format(series)

    if fmt == "yearfirst":
        parsed = pd.to_datetime(series, errors="coerce", yearfirst=True)
        if parsed.notna().sum() / n > THRESHOLD:
            return parsed

    elif fmt == "dayfirst":
        parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
        if parsed.notna().sum() / n > THRESHOLD:
            return parsed

    elif fmt == "monthfirst":
        parsed = pd.to_datetime(series, dayfirst=False, errors="coerce")
        if parsed.notna().sum() / n > THRESHOLD:
            return parsed

    # No separator detected — try generic strategies  ───────────────────────

    # Strategy 1: ISO / YYYY-MM-DD style
    try:
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().sum() / n > THRESHOLD:
            return parsed
    except Exception:
        pass

    # Strategy 2: dayfirst fallback (DD-MM-YYYY without separator detected)
    try:
        parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
        if parsed.notna().sum() / n > THRESHOLD:
            return parsed
    except Exception:
        pass

    # Strategy 3: integer-packed DDMMYYYY / MMDDYYYY (7–8 digit integer)
    try:
        s_str = series.dropna().astype(str).str.strip()
        if s_str.str.match(r"^\d{7,8}$").mean() > THRESHOLD:
            def _unpack(v):
                try:
                    v_str = str(int(float(str(v)))).zfill(8)  # pad to 8 digits
                    # Try DDMMYYYY
                    day, month, year = int(v_str[0:2]), int(v_str[2:4]), int(v_str[4:8])
                    if 1 <= month <= 12 and 1 <= day <= 31 and year >= 1900:
                        return pd.Timestamp(year=year, month=month, day=day)
                    
                    # Try YYYYMMDD fallback if DDMMYYYY fails
                    year, month, day = int(v_str[0:4]), int(v_str[4:6]), int(v_str[6:8])
                    if 1 <= month <= 12 and 1 <= day <= 31 and year >= 1900:
                        return pd.Timestamp(year=year, month=month, day=day)
                except Exception:
                    pass
                return pd.NaT
            parsed = series.apply(_unpack)
            if parsed.notna().sum() / n > THRESHOLD:
                return parsed
    except Exception:
        pass

    # Strategy 4: Unix Timestamps (Seconds or Milliseconds)
    try:
        # Check if they look like timestamps (e.g. 10^9 or 10^12)
        s_num = pd.to_numeric(series, errors="coerce").dropna()
        if not s_num.empty:
            mean_val = s_num.mean()
            # Seconds (e.g. 1.6e9)
            if 1e9 < mean_val < 3e9:
                parsed = pd.to_datetime(series, unit='s', errors="coerce")
                if parsed.notna().sum() / n > THRESHOLD:
                    return parsed
            # Milliseconds (e.g. 1.6e12)
            elif 1e12 < mean_val < 3e12:
                parsed = pd.to_datetime(series, unit='ms', errors="coerce")
                if parsed.notna().sum() / n > THRESHOLD:
                    return parsed
    except Exception:
        pass

    # Strategy 5: Mixed-format (pandas ≥ 2.0 feature)
    try:
        parsed = pd.to_datetime(series, format="mixed",
                                dayfirst=True, errors="coerce")
        if parsed.notna().sum() / n > THRESHOLD:
            # Final sanity check: if all dates are 1970, it's likely a parsing error
            if (parsed.dt.year == 1970).all():
                return None
            return parsed
    except Exception:
        pass

    return None   # unable to parse


def _is_revenue_col(col_name: str) -> bool:
    cl = col_name.lower()
    return any(k in cl for k in _REVENUE_KEYWORDS)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TOOL
# ─────────────────────────────────────────────────────────────────────────────

def clean_data(filepath: str) -> tuple[pd.DataFrame, dict]:
    """
    MCP Tool Call: Data Cleaning Pipeline.

    Steps:
        1. Load CSV
        2. Remove duplicate rows
        3. Strip whitespace from string columns
        4. Coerce numeric columns (remove $, ₹, commas, etc.)
        5a. Smart date parsing — named date columns (any string format)
        5b. Reconstruct __date__ from integer year / month / day columns
        5c. Integer-packed date column fallback
        6. Remove negative values from revenue / price columns
        7. Impute missing values (median for numeric, mode for categorical)
        8. Cap outliers (IQR × 3.0; revenue only upper tail)
        9. Reset index

    Returns:
        (cleaned_df, report_dict)
    """
    report = {
        "tool": "data_cleaner",
        "timestamp": datetime.utcnow().isoformat(),
        "steps": [],
        "original_shape": None,
        "clean_shape": None,
        "issues_fixed": 0
    }

    # ── Step 1: Load ──────────────────────────────────────────────────────
    df = pd.read_csv(filepath, encoding="utf-8", encoding_errors="replace")
    report["original_shape"] = {"rows": len(df), "cols": len(df.columns)}
    report["columns"] = df.columns.tolist()

    # ── Step 2: Remove duplicates ─────────────────────────────────────────
    # Preserve all rows by default. Duplicates can be valid repeated transactions!
    before = len(df)
    duplicates = df[df.duplicated(keep=False)]
    
    # Log but DO NOT remove automatically
    print("Duplicate rows detected:", len(duplicates))
    removed = 0
    
    report["steps"].append({"step": "remove_duplicates", "removed_rows": removed, "detected": len(duplicates)})
    report["issues_fixed"] += removed

    # ── Step 3: Strip whitespace ──────────────────────────────────────────
    obj_cols = df.select_dtypes(include="object").columns.tolist()
    for col in obj_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": np.nan, "None": np.nan, "": np.nan})
    report["steps"].append({"step": "strip_whitespace",
                             "columns_processed": len(obj_cols)})

    # ── Step 4: Coerce numeric columns ────────────────────────────────────
    # Robustly strip all non-numeric characters (except digits, negative signs, decimals)
    coerced = []
    for col in df.columns:
        if df[col].dtype == object:
            # SKIP if this column name suggests it is a DATE or PRODUCT column
            if any(k in col.lower() for k in _DATE_KEYWORDS + _PRODUCT_KEYWORDS):
                continue

            # Clean string, removing anything not digit, minus, or dot
            cleaned_str = (df[col].astype(str)
                           .str.replace(r'[^\d.-]', '', regex=True)
                           .str.strip())
            # Handle empty strings that might become from pure text replacement
            cleaned_str = cleaned_str.replace('', np.nan)
            
            converted = pd.to_numeric(cleaned_str, errors="coerce")
            # Accept if ≥ 50% converted successfully (avoids turning text cols numeric)
            if converted.notna().sum() / max(len(df), 1) >= 0.50:
                df[col] = converted
                coerced.append(col)
    report["steps"].append({"step": "coerce_numerics", "columns": coerced})

    # ── Step 5a: Parse date-named string columns ──────────────────────────
    date_cols = []
    for col in df.columns:
        if df[col].dtype == object:
            if any(k in col.lower() for k in _DATE_KEYWORDS):
                parsed = _smart_parse_date(df[col])
                if parsed is not None:
                    df[col] = parsed
                    date_cols.append(col)

    # ── Step 5b: Reconstruct __date__ from year/month/day integer cols ────
    _year_col  = next((c for c in df.columns if c.lower() == "year"),  None)
    _month_col = next((c for c in df.columns if c.lower() == "month"), None)
    _day_col   = next((c for c in df.columns if c.lower() == "day"),   None)
    
    # Check if existing date columns are actually valid (not just 1970 epoch)
    _has_valid_date = False
    for c in date_cols:
        if c in df.columns and pd.api.types.is_datetime64_any_dtype(df[c]):
            # If all dates are 1970, consider it invalid
            if not (df[c].dt.year == 1970).all():
                _has_valid_date = True
                break

    if not _has_valid_date and _year_col and _month_col:
        try:
            _day_s = df[_day_col] if _day_col else 1
            reconstructed = pd.to_datetime(
                dict(year=df[_year_col], month=df[_month_col], day=_day_s),
                errors="coerce"
            )
            if reconstructed.notna().sum() / max(len(df), 1) > 0.5:
                df["__date__"] = reconstructed
                date_cols.append("__date__")
        except Exception:
            pass

    # ── Step 5c: Integer-packed date column fallback ──────────────────────
    # Handles columns named 'date' / 'Date' that were coerced to int in Step 4.
    if not date_cols:
        for col in df.columns:
            if any(k in col.lower() for k in _DATE_KEYWORDS):
                if pd.api.types.is_numeric_dtype(df[col]):
                    parsed = _smart_parse_date(df[col].astype(str))
                    if parsed is not None:
                        df[col] = parsed
                        date_cols.append(col)
                        break

    report["steps"].append({"step": "parse_dates", "columns": date_cols})

    # ── Step 6: Negative values (Data Integrity) ──────────────
    # We do NOT remove negative values anymore to preserve data integrity.
    # Negatives in revenue/sales are treated as returns/refunds.
    report["steps"].append({"step": "remove_negatives", "columns": []})

    # ── Step 7: Impute missing values ─────────────────────────────────────
    null_before = int(df.isnull().sum().sum())
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())

    for col in df.select_dtypes(include="object").columns:
        if df[col].isnull().any():
            mode_val = df[col].mode()
            if not mode_val.empty:
                df[col] = df[col].fillna(mode_val[0])

    null_after = int(df.isnull().sum().sum())
    report["steps"].append({
        "step": "impute_nulls",
        "nulls_before": null_before,
        "nulls_after": null_after,
        "imputed": null_before - null_after
    })
    report["issues_fixed"] += (null_before - null_after)

    # ── Step 8: Cap outliers (IQR × 3) ───────────────────────────────────
    # Revenue/price cols: only cap upper tail (lower floor = 0).
    # Other numeric cols: cap both tails symmetrically.
    outlier_cols = []
    for col in df.select_dtypes(include=[np.number]).columns:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        if IQR > 0:
            upper = Q3 + 3.0 * IQR
            lower = 0.0 if _is_revenue_col(col) else Q1 - 3.0 * IQR
            n_out = int(((df[col] < lower) | (df[col] > upper)).sum())
            if n_out > 0:
                df[col] = df[col].clip(lower=lower, upper=upper)
                outlier_cols.append({"col": col, "capped": n_out})
                report["issues_fixed"] += n_out
    report["steps"].append({"step": "cap_outliers", "columns": outlier_cols})

    # ── Step 9: Reset index ───────────────────────────────────────────────
    df = df.reset_index(drop=True)
    report["clean_shape"] = {"rows": len(df), "cols": len(df.columns)}
    report["steps"].append({"step": "reset_index"})

    return df, report
