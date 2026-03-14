from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import polars as pl

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

DATE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"),   "%Y-%m-%d"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"),   "%m/%d/%Y"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"),   "%m-%d-%Y"),
    (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "%d.%m.%Y"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"),   "%Y/%m/%d"),
]

CRITICAL_COLS = frozenset({
    "rating", "performance_rating", "score", "grade", "review",
    "eval", "evaluation", "stars", "salary", "compensation", "pay",
})
NAME_COLS = frozenset({
    "name", "first", "last", "firstname", "lastname", "fullname",
    "full_name", "first_name", "last_name", "employee_name", "emp_name",
})
EMAIL_COLS  = frozenset({"email", "work_email", "mail", "e_mail", "email_address"})
ID_COLS     = frozenset({"id", "emp_id", "employee_id", "user_id", "uid", "record_id"})
DATE_COLS   = frozenset({
    "date", "hire_date", "start_date", "end_date", "dob", "birth_date",
    "join_date", "created_at", "updated_at", "termination_date",
})
PHONE_COLS  = frozenset({"phone", "telephone", "mobile", "cell", "phone_number", "contact"})

RATING_MAP: dict[str, float] = {
    "excellent": 5.0, "outstanding": 5.0, "exceptional": 5.0,
    "very good": 4.5, "above average": 4.5, "superior": 4.5,
    "good": 4.0,      "proficient": 4.0,   "competent": 4.0,
    "satisfactory": 3.5, "adequate": 3.5,  "acceptable": 3.5,
    "average": 3.0,   "meets expectations": 3.0, "standard": 3.0,
    "fair": 2.5,      "below average": 2.5, "marginal": 2.5,
    "needs improvement": 2.0, "poor": 2.0, "developing": 2.0,
    "unsatisfactory": 1.5,    "unacceptable": 1.5,
    "failing": 1.0,   "critical": 1.0,
}
_RATING_NUM_MAP: list[tuple[float, str]] = sorted(
    {v: k.title() for k, v in RATING_MAP.items()}.items()
)

BOOLEAN_TRUE  = frozenset({"yes", "y", "true",  "1", "t", "on",  "active",   "enabled"})
BOOLEAN_FALSE = frozenset({"no",  "n", "false", "0", "f", "off", "inactive", "disabled"})

NULL_SENTINELS = frozenset({
    "", "null", "none", "n/a", "na", "nan", "-", "--",
    "missing", "undefined", "unknown", "nil", "tbd",
})

COMMON_DOMAIN_FIXES: dict[str, str] = {
    "gmial.com": "gmail.com",   "gmal.com":    "gmail.com",
    "gmaill.com": "gmail.com",  "gamil.com":   "gmail.com",
    "gnail.com": "gmail.com",   "gmail.con":   "gmail.com",
    "yahooo.com": "yahoo.com",  "yaho.com":    "yahoo.com",
    "yahoo.con": "yahoo.com",   "hotmal.com":  "hotmail.com",
    "hotmial.com": "hotmail.com","hotmail.con": "hotmail.com",
    "outlok.com": "outlook.com","outllook.com": "outlook.com",
    "outlook.con": "outlook.com",
}

TO_BE_DETERMINED = "TO_BE_DETERMINED"

_PHONE_DIGITS = re.compile(r"\d")
_CURRENCY_RE  = re.compile(r"^[\$€£¥₹]?\s*([\d,]+\.?\d*)\s*$")

_NAME_PARTICLES = frozenset({
    "van", "de", "der", "den", "von", "del", "di", "da",
    "la", "le", "les", "du", "des", "al", "el", "bin", "binti",
})

QuarantineReasons = dict[int, list[str]]


def _smart_title(s: str) -> str:
    words = s.split()
    out = []
    for i, w in enumerate(words):
        if i > 0 and w.lower() in _NAME_PARTICLES:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _col_type(col: str) -> str:
    c = col.lower().replace(" ", "_").strip()
    if c in ID_COLS or c.endswith("_id"):
        return "id"
    if c in CRITICAL_COLS or any(k in c for k in CRITICAL_COLS):
        return "critical"
    if c in NAME_COLS or any(k in c for k in NAME_COLS):
        return "name"
    if c in EMAIL_COLS or any(k in c for k in EMAIL_COLS):
        return "email"
    if c in DATE_COLS or any(k in c for k in DATE_COLS):
        return "date"
    if c in PHONE_COLS or any(k in c for k in PHONE_COLS):
        return "phone"
    return "generic"


def _rec(changes, row, col, old, new, kind, reason):
    changes.append({
        "row":       int(row),
        "column":    col,
        "old_value": "" if old is None else str(old),
        "new_value": "" if new is None else str(new),
        "kind":      kind,
        "reason":    reason,
    })


def _quarantine(qr: QuarantineReasons, row_id: int, reason: str) -> None:
    qr.setdefault(row_id, []).append(reason)


def _detect_dominant_date_format(values: list[str]) -> Optional[str]:
    counts: dict[str, int] = {}
    for v in values:
        v = v.strip()
        if not v:
            continue
        for pattern, fmt in DATE_PATTERNS:
            if pattern.match(v):
                counts[fmt] = counts.get(fmt, 0) + 1
                break
    return max(counts, key=counts.get) if counts else None


def _is_numeric_col(col: pl.Series) -> bool:
    native = (
        pl.Float32, pl.Float64,
        pl.Int8, pl.Int16, pl.Int32, pl.Int64,
        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
    )
    if col.dtype in native:
        return True
    if col.dtype != pl.Utf8:
        return False
    non_null = col.drop_nulls()
    if non_null.len() == 0:
        return False
    ratio = non_null.cast(pl.Float64, strict=False).drop_nulls().len() / non_null.len()
    return ratio > 0.6


def _closest_rating_label(numeric: float) -> str:
    best_label, best_dist = "Average", float("inf")
    for val, label in _RATING_NUM_MAP:
        d = abs(val - numeric)
        if d < best_dist:
            best_dist, best_label = d, label
    return best_label


def _detect_email_naming_pattern(
    pairs: list[tuple[str, str]],
) -> Optional[dict]:
    votes: dict[tuple[str, str], int] = {}
    domain: Optional[str] = None

    for email, name in pairs:
        if not email or not name or "@" not in email:
            continue

        prefix_raw, dom = email.rsplit("@", 1)
        prefix = prefix_raw.lower().strip(".")
        if domain is None:
            domain = dom

        clean_name = name.replace(",", " ").strip()
        parts = [p for p in clean_name.split() if p]
        if len(parts) < 2:
            continue

        for name_order, (first, last) in [
            ("first_last", (parts[0],  parts[-1])),
            ("last_first", (parts[-1], parts[0])),
        ]:
            f, l = first.lower(), last.lower()
            candidates = {
                "first.last":  f"{f}.{l}",
                "first.linit": f"{f}.{l[0]}",
                "finit.last":  f"{f[0]}.{l}",
                "last.first":  f"{l}.{f}",
                "last.finit":  f"{l}.{f[0]}",
                "first":       f,
            }
            for pat, candidate in candidates.items():
                if prefix == candidate:
                    key = (pat, name_order)
                    votes[key] = votes.get(key, 0) + 1

    if not votes:
        return None

    best_key   = max(votes, key=votes.get)
    best_count = votes[best_key]
    total      = sum(votes.values())

    if best_count < 2 or best_count / total < 0.50:
        return None

    pattern, name_order = best_key
    return {
        "pattern":    pattern,
        "name_order": name_order,
        "domain":     domain,
        "confidence": best_count / total,
    }


def _email_from_name(name: str, info: dict) -> Optional[str]:
    parts = name.replace(",", " ").split()
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None

    if info["name_order"] == "first_last":
        first, last = parts[0], parts[-1]
    else:
        last, first = parts[0], parts[-1]

    f, l   = first.lower(), last.lower()
    domain = info["domain"]
    pat    = info["pattern"]

    prefix = {
        "first.last":  f"{f}.{l}",
        "first.linit": f"{f}.{l[0]}",
        "finit.last":  f"{f[0]}.{l}",
        "last.first":  f"{l}.{f}",
        "last.finit":  f"{l}.{f[0]}",
        "first":       f,
    }.get(pat)

    return f"{prefix}@{domain}" if prefix else None


def _name_from_email(email: str, info: dict) -> Optional[str]:
    if "@" not in email:
        return None

    prefix = email.rsplit("@", 1)[0].lower().strip(".")
    pat    = info["pattern"]

    first: Optional[str] = None
    last:  Optional[str] = None

    if pat == "first.last" and "." in prefix:
        parts = prefix.split(".", 1)
        first, last = parts[0], parts[1]
    elif pat == "first.linit" and "." in prefix:
        parts = prefix.split(".", 1)
        first = parts[0]
        last  = None
    elif pat == "finit.last" and "." in prefix:
        parts = prefix.split(".", 1)
        first = None
        last  = parts[1]
    elif pat == "last.first" and "." in prefix:
        parts = prefix.split(".", 1)
        last, first = parts[0], parts[1]
    elif pat == "last.finit" and "." in prefix:
        parts = prefix.split(".", 1)
        last  = parts[0]
        first = None
    elif pat == "first":
        first = prefix

    if not first or not last:
        return None

    first, last = first.capitalize(), last.capitalize()

    if info["name_order"] == "first_last":
        return f"{first} {last}"
    else:
        return f"{last} {first}"


def _fix_whitespace(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    str_cols = [c for c in df.columns if df[c].dtype == pl.Utf8 and c != "_row_id"]
    for col_name in str_cols:
        col      = df[col_name]
        stripped = col.str.strip_chars()
        mask     = col.is_not_null() & (col != stripped)
        for i in range(df.height):
            if mask[i]:
                _rec(ch, i, col_name, col[i], stripped[i], "fixed",
                     "Leading/trailing whitespace stripped.")
    if str_cols:
        df = df.with_columns(
            [pl.col(c).str.strip_chars().alias(c) for c in str_cols]
        )
    return df


def _fix_null_sentinels(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    str_cols = [c for c in df.columns if df[c].dtype == pl.Utf8 and c != "_row_id"]
    for col_name in str_cols:
        col  = df[col_name]
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is not None and v.strip().lower() in NULL_SENTINELS:
                _rec(ch, i, col_name, v, "", "fixed",
                     f"Null-sentinel '{v}' normalised to null.")
                vals[i] = None
                chg = True
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_numeric_strings(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    skip = frozenset({"id", "email", "phone", "date", "name"})
    for col_name in df.columns:
        if col_name == "_row_id" or _col_type(col_name) in skip:
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        non_null = col.drop_nulls().to_list()
        if len(non_null) < 3:
            continue
        if sum(1 for v in non_null if _CURRENCY_RE.match(str(v).strip())) / len(non_null) < 0.5:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            m = _CURRENCY_RE.match(v.strip())
            if m:
                cleaned = m.group(1).replace(",", "")
                if cleaned != v.strip():
                    _rec(ch, i, col_name, v, cleaned, "fixed",
                         "Currency symbol / thousand-separator removed.")
                    vals[i] = cleaned
                    chg = True
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_ratings(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    rating_kw = ("rating", "performance", "score", "eval", "grade", "stars")
    for col_name in df.columns:
        if col_name == "_row_id":
            continue
        if _col_type(col_name) != "critical":
            continue
        if not any(k in col_name.lower() for k in rating_kw):
            continue
        col  = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            vl      = v.strip().lower()
            matched = False
            for text_val, num_val in RATING_MAP.items():
                if text_val == vl or text_val in vl:
                    nv = str(num_val)
                    _rec(ch, i, col_name, v, nv, "fixed",
                         f"Text rating '{v}' → {num_val}.")
                    vals[i] = nv
                    chg = matched = True
                    break
            if not matched:
                try:
                    num = float(vl)
                    if num > 5.0:
                        _rec(ch, i, col_name, v, "5.0", "fixed",
                             f"Rating {v} > max 5 — clamped.")
                        vals[i] = "5.0"
                        chg = True
                    elif num < 0:
                        _rec(ch, i, col_name, v, "1.0", "fixed",
                             f"Negative rating {v} clamped to 1.0.")
                        vals[i] = "1.0"
                        chg = True
                except ValueError:
                    pass
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_type_coerce(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    for col_name in df.columns:
        if col_name == "_row_id":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        non_null = col.drop_nulls().to_list()
        if len(non_null) < 2:
            continue

        num_count  = sum(1 for v in non_null if _is_castable_float(v))
        text_count = sum(1 for v in non_null if v.strip().lower() in RATING_MAP)

        total = len(non_null)

        if text_count / total > 0.5 and num_count > 0 and num_count / total < 0.5:
            vals = col.to_list()
            chg  = False
            for i, v in enumerate(vals):
                if v is None:
                    continue
                if _is_castable_float(v) and v.strip().lower() not in RATING_MAP:
                    try:
                        num   = float(v.strip())
                        label = _closest_rating_label(num)
                        _rec(ch, i, col_name, v, label, "fixed",
                             f"Numeric {v} in text-rating column → '{label}'.")
                        vals[i] = label
                        chg = True
                    except ValueError:
                        pass
            if chg:
                df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))

        elif num_count / total > 0.5 and text_count > 0 and text_count / total < 0.5:
            vals = col.to_list()
            chg  = False
            for i, v in enumerate(vals):
                if v is None:
                    continue
                vl = v.strip().lower()
                for text_val, num_val in RATING_MAP.items():
                    if text_val == vl or text_val in vl:
                        nv = str(num_val)
                        _rec(ch, i, col_name, v, nv, "fixed",
                             f"Text label '{v}' in numeric column → {num_val}.")
                        vals[i] = nv
                        chg = True
                        break
            if chg:
                df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))

    return df


def _is_castable_float(v: str) -> bool:
    try:
        float(v.strip().replace(",", ""))
        return True
    except (ValueError, AttributeError):
        return False


def _fix_dates(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    target_fmt = "%Y-%m-%d"
    for col_name in df.columns:
        if col_name == "_row_id" or _col_type(col_name) != "date":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        non_null = [str(v) for v in col.drop_nulls().to_list()]
        dominant = _detect_dominant_date_format(non_null)
        if not dominant or dominant == target_fmt:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            vs = v.strip()
            try:
                nv = datetime.strptime(vs, dominant).strftime(target_fmt)
                if nv != vs:
                    _rec(ch, i, col_name, v, nv, "fixed",
                         "Date standardised to ISO 8601.")
                    vals[i] = nv
                    chg = True
            except ValueError:
                for _, fmt in DATE_PATTERNS:
                    try:
                        nv = datetime.strptime(vs, fmt).strftime(target_fmt)
                        _rec(ch, i, col_name, v, nv, "fixed",
                             "Date standardised to ISO 8601.")
                        vals[i] = nv
                        chg = True
                        break
                    except ValueError:
                        continue
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_emails(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    for col_name in df.columns:
        if col_name == "_row_id" or _col_type(col_name) != "email":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            original = v
            fixed    = v.strip().lower()
            if "@" in fixed:
                local, domain = fixed.rsplit("@", 1)
                domain = COMMON_DOMAIN_FIXES.get(domain, domain)
                fixed  = f"{local}@{domain}"
            if fixed != original:
                _rec(ch, i, col_name, original, fixed, "fixed",
                     "Email normalised (lowercase + domain correction).")
                vals[i] = fixed
                chg = True
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_phones(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    for col_name in df.columns:
        if col_name == "_row_id" or _col_type(col_name) != "phone":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            digits = "".join(_PHONE_DIGITS.findall(v))
            fmt    = None
            if len(digits) == 10:
                fmt = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            elif len(digits) == 11 and digits[0] == "1":
                fmt = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
            if fmt and fmt != v.strip():
                _rec(ch, i, col_name, v, fmt, "fixed",
                     "Phone number standardised.")
                vals[i] = fmt
                chg = True
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_booleans(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    for col_name in df.columns:
        if col_name == "_row_id":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        non_null = col.drop_nulls().to_list()
        if len(non_null) < 2:
            continue
        lowered = {str(v).strip().lower() for v in non_null if v}
        if not lowered.issubset(BOOLEAN_TRUE | BOOLEAN_FALSE) or len(lowered) < 2:
            continue
        vals = col.to_list()
        chg  = False
        for i, v in enumerate(vals):
            if v is None:
                continue
            vl = v.strip().lower()
            if vl in BOOLEAN_TRUE and v != "True":
                _rec(ch, i, col_name, v, "True", "fixed",
                     "Boolean normalised to 'True'.")
                vals[i] = "True"
                chg = True
            elif vl in BOOLEAN_FALSE and v != "False":
                _rec(ch, i, col_name, v, "False", "fixed",
                     "Boolean normalised to 'False'.")
                vals[i] = "False"
                chg = True
        if chg:
            df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
    return df


def _fix_cross_column(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    email_cols = [c for c in df.columns if _col_type(c) == "email"]
    name_cols  = [c for c in df.columns if _col_type(c) == "name"]

    if not email_cols or not name_cols:
        return df

    for email_col in email_cols:
        for name_col in name_cols:
            if df[email_col].dtype != pl.Utf8 or df[name_col].dtype != pl.Utf8:
                continue

            emails = df[email_col].to_list()
            names  = df[name_col].to_list()

            complete_pairs = [
                (e, n)
                for e, n in zip(emails, names)
                if e and n and "@" in e and EMAIL_RE.match(e)
            ]
            if len(complete_pairs) < 3:
                continue

            pattern_info = _detect_email_naming_pattern(complete_pairs)
            if not pattern_info:
                continue

            existing_emails = {
                e for e in emails
                if e and "@" in e and EMAIL_RE.match(e)
            }

            kind = "fixed" if pattern_info["confidence"] >= 0.80 else "warning"
            new_emails = list(emails)
            new_names  = list(names)
            chg        = False

            for i, (email, name) in enumerate(zip(emails, names)):
                if (not email) and name:
                    inferred = _email_from_name(name, pattern_info)
                    if (
                        inferred
                        and EMAIL_RE.match(inferred)
                        and inferred not in existing_emails
                    ):
                        _rec(ch, i, email_col, "", inferred, kind,
                             f"Email inferred from name '{name}' "
                             f"(pattern: {pattern_info['pattern']}, "
                             f"confidence: {pattern_info['confidence']:.0%}).")
                        new_emails[i] = inferred
                        existing_emails.add(inferred)
                        chg = True

                elif (not name) and email and EMAIL_RE.match(email):
                    inferred = _name_from_email(email, pattern_info)
                    if inferred:
                        _rec(ch, i, name_col, "", inferred, kind,
                             f"Name inferred from email '{email}' "
                             f"(pattern: {pattern_info['pattern']}, "
                             f"confidence: {pattern_info['confidence']:.0%}).")
                        new_names[i] = inferred
                        chg = True

            if chg:
                df = df.with_columns([
                    pl.Series(email_col, new_emails, dtype=pl.Utf8),
                    pl.Series(name_col,  new_names,  dtype=pl.Utf8),
                ])

    return df


def _fix_missing(
    df: pl.DataFrame,
    ch:  list,
    qr:  QuarantineReasons,
) -> pl.DataFrame:
    row_ids: list[int] = df["_row_id"].to_list()

    for col_name in df.columns:
        if col_name == "_row_id":
            continue
        col        = df[col_name]
        null_count = col.null_count()
        if null_count == 0:
            continue

        ct = _col_type(col_name)

        if ct in ("id", "name", "email", "phone", "date", "critical"):
            for i in range(df.height):
                if col[i] is None:
                    reason = (
                        f"Missing {ct.upper()} value in column '{col_name}' — "
                        "cannot be inferred automatically."
                    )
                    _quarantine(qr, row_ids[i], reason)
                    _rec(ch, i, col_name, "", "", "critical", reason)
            continue

        if _is_numeric_col(col):
            try:
                numeric  = col.cast(pl.Float64, strict=False)
                med_val  = numeric.median()
                if med_val is None:
                    continue
                med      = round(float(med_val), 2)
                valid    = numeric.drop_nulls().to_list()
                all_int  = all(v == int(v) for v in valid if v is not None)
                fill_str = str(int(med)) if all_int else str(med)
                vals     = col.to_list()
                chg      = False
                for i in range(df.height):
                    if vals[i] is None:
                        _rec(ch, i, col_name, "", fill_str, "warning",
                             f"Missing numeric filled with column median ({fill_str}).")
                        vals[i] = fill_str
                        chg = True
                if chg:
                    df = df.with_columns(pl.Series(col_name, vals, dtype=pl.Utf8))
                continue
            except Exception:
                pass

        if col.dtype == pl.Utf8:
            non_null = col.drop_nulls()
            if non_null.len() == 0:
                continue
            mode_vals  = non_null.mode().to_list()
            mode_val   = mode_vals[0] if mode_vals else None
            if mode_val is None:
                continue
            mode_count = non_null.to_list().count(mode_val)
            mode_ratio = mode_count / non_null.len()

            if mode_ratio > 0.40:
                vals = col.to_list()
                chg  = False
                for i in range(df.height):
                    if vals[i] is None:
                        _rec(ch, i, col_name, "", str(mode_val), "warning",
                             f"Missing text filled with dominant mode "
                             f"'{mode_val}' ({mode_ratio:.0%} frequency).")
                        vals[i] = str(mode_val)
                        chg = True
                if chg:
                    df = df.with_columns(
                        pl.Series(col_name, vals, dtype=pl.Utf8)
                    )
            else:
                for i in range(df.height):
                    if col[i] is None:
                        _rec(ch, i, col_name, "", "", "warning",
                             f"Missing value in '{col_name}': "
                             "no dominant mode — flagged for review.")
    return df


def _fix_casing(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    skip_types = frozenset({"id", "email", "date", "phone", "critical"})
    for col_name in df.columns:
        if col_name == "_row_id":
            continue
        ct = _col_type(col_name)
        if ct in skip_types:
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8 or _is_numeric_col(col):
            continue
        vals = col.drop_nulls().to_list()
        if len(vals) < 3:
            continue

        lower_c = sum(1 for v in vals if v == v.lower() and v != v.upper())
        upper_c = sum(1 for v in vals if v == v.upper() and v != v.lower())
        title_c = sum(1 for v in vals if v == v.title())
        total   = lower_c + upper_c + title_c
        if total == 0:
            continue

        max_style = max(lower_c, upper_c, title_c)
        if max_style / total < 0.50 or max_style == total:
            continue

        if ct == "name" or max_style == title_c:
            fn    = _smart_title
            label = "Title Case"
        elif max_style == lower_c:
            fn    = str.lower
            label = "lowercase"
        else:
            fn    = str.upper
            label = "UPPERCASE"

        col_vals = col.to_list()
        chg      = False
        for i, v in enumerate(col_vals):
            if v is None:
                continue
            fixed = fn(v)
            if fixed != v:
                _rec(ch, i, col_name, v, fixed, "fixed",
                     f"Casing standardised to {label}.")
                col_vals[i] = fixed
                chg = True
        if chg:
            df = df.with_columns(
                pl.Series(col_name, col_vals, dtype=pl.Utf8)
            )
    return df


def _validate_emails(
    df: pl.DataFrame,
    ch:  list,
    qr:  QuarantineReasons,
) -> None:
    row_ids: list[int] = df["_row_id"].to_list()
    for col_name in df.columns:
        if col_name == "_row_id" or _col_type(col_name) != "email":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        for i in range(df.height):
            v = col[i]
            if v is None:
                continue
            if not EMAIL_RE.match(v.strip()):
                reason = (
                    f"Email '{v}' in '{col_name}' remains invalid "
                    "after auto-correction — manual fix required."
                )
                _quarantine(qr, row_ids[i], reason)
                _rec(ch, i, col_name, v, "", "critical", reason)


def autofix_dataframe(
    df: pl.DataFrame,
) -> tuple[pl.DataFrame, list[dict], pl.DataFrame]:
    df = df.with_row_index("_row_id")

    content_cols = {c: pl.Utf8 for c in df.columns if c != "_row_id"}
    df = df.cast(content_cols)

    ch: list[dict]        = []
    qr: QuarantineReasons = {}

    df = _fix_whitespace(df, ch)
    df = _fix_null_sentinels(df, ch)
    df = _fix_numeric_strings(df, ch)
    df = _fix_ratings(df, ch)
    df = _fix_type_coerce(df, ch)
    df = _fix_dates(df, ch)
    df = _fix_emails(df, ch)
    df = _fix_phones(df, ch)
    df = _fix_booleans(df, ch)
    df = _fix_cross_column(df, ch)
    df = _fix_missing(df, ch, qr)
    df = _fix_casing(df, ch)

    _validate_emails(df, ch, qr)

    q_ids = set(qr.keys())

    if q_ids:
        q_ids_list    = list(q_ids)
        q_df          = df.filter(pl.col("_row_id").is_in(q_ids_list))
        clean_df_raw  = df.filter(~pl.col("_row_id").is_in(q_ids_list))

        reasons = pl.Series(
            "_issue_reason",
            ["; ".join(qr.get(int(rid), ["Unknown issue"]))
             for rid in q_df["_row_id"].to_list()],
            dtype=pl.Utf8,
        )
        quarantine_df = q_df.with_columns(reasons)

        content_q = [
            c for c in quarantine_df.columns
            if c not in ("_row_id", "_issue_reason")
        ]
        tbd_exprs = []
        for c in content_q:
            if quarantine_df[c].dtype == pl.Utf8:
                tbd_exprs.append(
                    pl.when(pl.col(c).is_null())
                    .then(pl.lit(TO_BE_DETERMINED))
                    .otherwise(pl.col(c))
                    .alias(c)
                )
        if tbd_exprs:
            quarantine_df = quarantine_df.with_columns(tbd_exprs)

    else:
        clean_df_raw = df
        quarantine_df = df.clear().with_columns(
            pl.lit(None).cast(pl.Utf8).alias("_issue_reason")
        )

    clean_row_ids       = clean_df_raw["_row_id"].to_list()
    row_id_to_clean_idx = {int(rid): idx for idx, rid in enumerate(clean_row_ids)}

    display_changes = [
        {**c, "row": row_id_to_clean_idx[c["row"]]}
        for c in ch
        if c["row"] not in q_ids and c["row"] in row_id_to_clean_idx
    ]

    clean_df = clean_df_raw.drop("_row_id")

    logger.info(
        "Autofix | fixes=%d | clean=%d | quarantine=%d",
        len(ch), clean_df.height, quarantine_df.height,
    )
    return clean_df, display_changes, quarantine_df