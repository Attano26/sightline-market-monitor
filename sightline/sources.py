"""Fetchers for free, key-less public data sources.

Every fetcher returns plain Python data and never raises on a missing series:
a gap is returned as an empty list so the dashboard can show "no data".
"""

from __future__ import annotations

import io
import time

import pandas as pd
import requests

from . import config

TIMEOUT = 60
HEADERS = {"User-Agent": "sightline-market-monitor/0.1"}


def _get(url: str, params: dict | None = None, retries: int = 3) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def _points(df: pd.DataFrame, date_col: str, value_col: str) -> list[dict]:
    df = df[[date_col, value_col]].dropna()
    return [{"date": str(d), "value": round(float(v), 4)} for d, v in zip(df[date_col], df[value_col])]


# ---------- BIS: policy rates, house prices, exchange rates ----------

def _bis(dataflow: str, key: str, start: str) -> pd.DataFrame | None:
    r = _get(f"https://stats.bis.org/api/v1/data/{dataflow}/{key}/all",
             {"startPeriod": start, "format": "csv"})
    if r is None or not r.text.startswith("FREQ"):
        return None
    df = pd.read_csv(io.StringIO(r.text))
    if df.empty or "OBS_VALUE" not in df:
        return None
    return df


def policy_rate(iso2: str) -> list[dict]:
    df = _bis("WS_CBPOL", f"M.{iso2}", f"{config.HISTORY_START_YEAR}-01")
    return [] if df is None else _points(df, "TIME_PERIOD", "OBS_VALUE")


def house_prices(iso2: str) -> list[dict]:
    """Real residential property price index (2010 = 100), quarterly."""
    df = _bis("WS_SPP", f"Q.{iso2}.R.628", f"{config.HISTORY_START_YEAR}-Q1")
    return [] if df is None else _points(df, "TIME_PERIOD", "OBS_VALUE")


def exchange_rate(iso2: str, currency: str) -> list[dict]:
    """Local currency per USD, monthly average."""
    df = _bis("WS_XRU", f"M.{iso2}.{currency}.A", f"{config.HISTORY_START_YEAR}-01")
    return [] if df is None else _points(df, "TIME_PERIOD", "OBS_VALUE")


# ---------- FRED: global commodity prices ----------

def commodity(series_id: str) -> list[dict]:
    r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series_id})
    if r is None:
        return []
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["date"] >= f"{config.HISTORY_START_YEAR}-01-01"]
    df["date"] = df["date"].str[:7]
    return _points(df, "date", "value")


# ---------- World Bank: annual indicators ----------

def world_bank(iso3_list: list[str], indicator: str) -> dict[str, list[dict]]:
    r = _get(f"https://api.worldbank.org/v2/country/{';'.join(iso3_list)}/indicator/{indicator}",
             {"format": "json", "per_page": 2000, "date": f"{config.HISTORY_START_YEAR}:2030"})
    out: dict[str, list[dict]] = {c: [] for c in iso3_list}
    if r is None:
        return out
    payload = r.json()
    if len(payload) < 2 or payload[1] is None:
        return out
    for row in payload[1]:
        if row["value"] is not None and row["countryiso3code"] in out:
            out[row["countryiso3code"]].append({"date": row["date"], "value": round(row["value"], 3)})
    for c in out:
        out[c].sort(key=lambda p: p["date"])
    return out


# ---------- IMF World Economic Outlook (includes forecasts) ----------

def imf(iso3_list: list[str], indicator: str) -> dict[str, list[dict]]:
    r = _get(f"https://www.imf.org/external/datamapper/api/v1/{indicator}/{'/'.join(iso3_list)}")
    out: dict[str, list[dict]] = {c: [] for c in iso3_list}
    if r is None:
        return out
    values = r.json().get("values", {}).get(indicator, {})
    for c in iso3_list:
        series = values.get(c, {})
        out[c] = [{"date": y, "value": round(float(v), 3)} for y, v in sorted(series.items())
                  if int(y) >= config.HISTORY_START_YEAR and v is not None]
    return out


# ---------- UN Comtrade: fenestration product imports ----------

def imports(reporter_code: int, years: list[int]) -> dict[str, list[dict]]:
    """Annual import value (USD) per product code, from the public preview API."""
    out: dict[str, list[dict]] = {code: [] for code in config.TRADE_CODES}
    r = _get("https://comtradeapi.un.org/public/v1/preview/C/A/HS", {
        "reporterCode": reporter_code,
        "period": ",".join(str(y) for y in years),
        "partnerCode": 0,
        "cmdCode": ",".join(config.TRADE_CODES),
        "flowCode": "M",
    })
    if r is None:
        return out
    for row in r.json().get("data", []) or []:
        code = row.get("cmdCode")
        value = row.get("primaryValue")
        if code in out and value:
            out[code].append({"date": str(row["refYear"]), "value": float(value)})
    for code in out:
        # The preview can return duplicate rows (e.g. several customs regimes); keep the largest.
        best: dict[str, float] = {}
        for p in out[code]:
            best[p["date"]] = max(best.get(p["date"], 0.0), p["value"])
        out[code] = [{"date": d, "value": v} for d, v in sorted(best.items())]
    time.sleep(1.5)  # stay polite with the public endpoint
    return out
