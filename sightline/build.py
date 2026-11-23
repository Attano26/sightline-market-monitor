"""Runs the whole Sightline pipeline: fetch -> forecast -> score -> web/data/sightline.json.

    python -m sightline.build            # TimesFM if installed, else the fallback model
    python -m sightline.build --no-timesfm
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from . import config, forecast, outlook, sources

OUT = Path(__file__).resolve().parent.parent / "web" / "data" / "sightline.json"


def log(msg: str) -> None:
    print(f"[sightline] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-timesfm", action="store_true", help="use the lightweight fallback forecaster")
    args = ap.parse_args()

    # Last published data: used when a source refuses this run (some block cloud servers).
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    prev_countries = {c["iso2"]: c for c in previous.get("countries", [])}
    prev_commodities = {c["id"]: c for c in previous.get("commodities", [])}
    carried: set[str] = set()

    def keep(new, old, source: str):
        """Return new data, or the previous run's data (and note it) if the source returned nothing."""
        if new or not old:
            return new
        carried.add(source)
        return old

    model = forecast.Forecaster(use_timesfm=not args.no_timesfm)
    log(f"forecast model: {model.name}")
    iso3 = [c["iso3"] for c in config.COUNTRIES]
    this_year = dt.date.today().year

    log("World Bank + IMF ...")
    wb = {code: sources.world_bank(iso3, code) for code in config.WORLD_BANK}
    imf = {code: sources.imf(iso3, code) for code in config.IMF}

    countries = []
    for c in config.COUNTRIES:
        log(f"{c['name']} ...")
        prev = prev_countries.get(c["iso2"], {})
        prev_s = prev.get("series", {})
        old = lambda key: (prev_s.get(key) or {}).get("history", []) if isinstance(prev_s.get(key), dict) else prev_s.get(key, [])
        monthly = {
            "policy_rate":   keep(sources.policy_rate(c["iso2"]), old("policy_rate"), "BIS"),
            "house_prices":  keep(sources.house_prices(c["iso2"]), old("house_prices"), "BIS"),
            "exchange_rate": keep(sources.exchange_rate(c["iso2"], c["currency"]), old("exchange_rate"), "BIS"),
        }
        series = {}
        for key, hist in monthly.items():
            freq = "Q" if key == "house_prices" else "M"
            horizon = config.FORECAST_HORIZON_MONTHS // 3 if freq == "Q" else config.FORECAST_HORIZON_MONTHS
            series[key] = {"history": hist, "forecast": model.forecast(hist, horizon, freq), "freq": freq}
        series["wb_industry_growth"] = keep(wb["NV.IND.TOTL.KD.ZG"][c["iso3"]], old("wb_industry_growth"), "World Bank")
        series["wb_gfcf_growth"] = keep(wb["NE.GDI.FTOT.KD.ZG"][c["iso3"]], old("wb_gfcf_growth"), "World Bank")
        series["wb_urban_growth"] = keep(wb["SP.URB.GROW"][c["iso3"]], old("wb_urban_growth"), "World Bank")
        series["imf_gdp_growth"] = keep(imf["NGDP_RPCH"][c["iso3"]], old("imf_gdp_growth"), "IMF")
        series["wb_investment_ratio"] = keep(wb["NE.GDI.TOTL.ZS"][c["iso3"]], old("wb_investment_ratio"), "World Bank")

        trade = sources.imports(c["comtrade"], list(range(this_year - 10, this_year)))
        prev_trade = prev.get("trade", {})
        trade = {code: keep(vals, prev_trade.get(code, []), "UN Comtrade") for code, vals in trade.items()}
        country = {**c, "series": series, "trade": trade}
        country["outlook"] = outlook.score(country)
        countries.append(country)

    log("commodities ...")
    commodities = []
    for sid, name in config.COMMODITIES.items():
        hist = keep(sources.commodity(sid), prev_commodities.get(sid, {}).get("history", []), "FRED")
        commodities.append({"id": sid, "name": name, "history": hist,
                            "forecast": model.forecast(hist, config.FORECAST_HORIZON_MONTHS, "M")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "model": model.name,
        "carried_over": sorted(carried),
        "trade_codes": config.TRADE_CODES,
        "weights": config.WEIGHTS,
        "countries": countries,
        "commodities": commodities,
    }, indent=1), encoding="utf-8")
    log(f"wrote {OUT}")
    if carried:
        log(f"kept last good data for: {', '.join(sorted(carried))} (source refused this run)")
    for c in countries:
        o = c["outlook"]
        log(f"  {c['name']:<15} {o['label']:<12} {o['score']:+4d}  ({o['coverage']})")


if __name__ == "__main__":
    main()
