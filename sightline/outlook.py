"""Turns a country's indicators into an outlook score (-100..+100) and plain-language signals.

Each signal is squashed to -1..+1 with tanh(x / scale), so one extreme number cannot dominate.
Missing signals are skipped and the remaining weights are rescaled.
The scales and thresholds are judgement calls: tune them in config.py / here as you learn.
"""

from __future__ import annotations

import datetime as dt
import math

from . import config


def _squash(x: float, scale: float) -> float:
    return math.tanh(x / scale)


def _pct(new: float, old: float) -> float:
    return (new / old - 1) * 100 if old else 0.0


def _house_prices(s: dict) -> dict | None:
    hist, fc = s.get("history", []), s.get("forecast", [])
    if len(hist) < 5:
        return None
    yoy = _pct(hist[-1]["value"], hist[-5]["value"])
    ahead = _pct(fc[min(3, len(fc) - 1)]["value"], hist[-1]["value"]) if fc else yoy
    value = _squash(0.5 * yoy + 0.5 * ahead, 5)
    return {"value": value, "text": f"Real house prices {yoy:+.1f}% vs a year ago; forecast {ahead:+.1f}% over the next 4 quarters."}


def _rates(s: dict) -> dict | None:
    hist, fc = s.get("history", []), s.get("forecast", [])
    if len(hist) < 13:
        return None
    past = hist[-1]["value"] - hist[-13]["value"]
    ahead = (fc[-1]["value"] - hist[-1]["value"]) if fc else 0.0
    value = _squash(-(past + 0.5 * ahead), 1.5)
    direction = "cut" if past < -0.05 else "raised" if past > 0.05 else "held"
    return {"value": value, "text": f"Policy rate {hist[-1]['value']:.2f}%, {direction} by {abs(past):.2f} pp over 12 months (lower rates support building)."}


def _investment(inv: list[dict], gdp: list[dict]) -> dict | None:
    year = dt.date.today().year
    by_year_inv = {int(p["date"]): p["value"] for p in inv}
    by_year_gdp = {int(p["date"]): p["value"] for p in gdp}
    parts, texts = [], []
    if year in by_year_inv and year + 2 in by_year_inv:
        delta = by_year_inv[year + 2] - by_year_inv[year]
        parts.append(_squash(delta, 1.0))
        texts.append(f"IMF sees investment at {by_year_inv[year + 2]:.1f}% of GDP in {year + 2} ({delta:+.1f} pp)")
    if year + 1 in by_year_gdp:
        g = by_year_gdp[year + 1]
        parts.append(_squash(g - 2.5, 2.5))
        texts.append(f"GDP growth forecast {g:.1f}% for {year + 1}")
    if not parts:
        return None
    return {"value": sum(parts) / len(parts), "text": "; ".join(texts) + "."}


def _construction(industry: list[dict], gfcf: list[dict]) -> dict | None:
    latest = [s[-1] for s in (industry, gfcf) if s]
    if not latest:
        return None
    avg = sum(p["value"] for p in latest) / len(latest)
    years = "/".join(sorted({p["date"] for p in latest}))
    return {"value": _squash(avg, 5), "text": f"Industry & fixed-investment growth averaged {avg:+.1f}% in {years} (World Bank)."}


def _imports(trade: dict[str, list[dict]]) -> dict | None:
    totals: dict[str, float] = {}
    for series in trade.values():
        for p in series:
            totals[p["date"]] = totals.get(p["date"], 0.0) + p["value"]
    years = sorted(totals)
    if len(years) < 4:
        return None
    last, base = years[-1], years[-4]
    cagr = ((totals[last] / totals[base]) ** (1 / 3) - 1) * 100 if totals[base] else 0.0
    return {"value": _squash(cagr, 10), "text": f"Fenestration product imports ${totals[last] / 1e6:,.0f}M in {last}, {cagr:+.1f}% a year since {base}."}


def score(country: dict) -> dict:
    s = country["series"]
    signals = {
        "house_prices": _house_prices(s["house_prices"]),
        "rates":        _rates(s["policy_rate"]),
        "investment":   _investment(s["imf_investment"], s["imf_gdp_growth"]),
        "construction": _construction(s["wb_industry_growth"], s["wb_gfcf_growth"]),
        "imports":      _imports(country["trade"]),
    }
    available = {k: v for k, v in signals.items() if v is not None}
    total_w = sum(config.WEIGHTS[k] for k in available)
    raw = sum(config.WEIGHTS[k] * v["value"] for k, v in available.items()) / total_w if total_w else 0.0
    points = round(raw * 100)
    label = ("Expanding" if points > config.EXPANDING_ABOVE
             else "Contracting" if points < config.CONTRACTING_BELOW else "Stable")
    return {
        "score": points,
        "label": label,
        "coverage": f"{len(available)}/{len(signals)} signals",
        "signals": {k: (None if v is None else {"value": round(v["value"], 3), "text": v["text"]})
                    for k, v in signals.items()},
    }
