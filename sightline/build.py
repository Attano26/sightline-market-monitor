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
        monthly = {
            "policy_rate":   sources.policy_rate(c["iso2"]),
            "house_prices":  sources.house_prices(c["iso2"]),
            "exchange_rate": sources.exchange_rate(c["iso2"], c["currency"]),
        }
        series = {}
        for key, hist in monthly.items():
            freq = "Q" if key == "house_prices" else "M"
            horizon = config.FORECAST_HORIZON_MONTHS // 3 if freq == "Q" else config.FORECAST_HORIZON_MONTHS
            series[key] = {"history": hist, "forecast": model.forecast(hist, horizon, freq), "freq": freq}
        series["wb_industry_growth"] = wb["NV.IND.TOTL.KD.ZG"][c["iso3"]]
        series["wb_gfcf_growth"] = wb["NE.GDI.FTOT.KD.ZG"][c["iso3"]]
        series["wb_urban_growth"] = wb["SP.URB.GROW"][c["iso3"]]
        series["imf_gdp_growth"] = imf["NGDP_RPCH"][c["iso3"]]
        series["wb_investment_ratio"] = wb["NE.GDI.TOTL.ZS"][c["iso3"]]

        trade = sources.imports(c["comtrade"], list(range(this_year - 10, this_year)))
        country = {**c, "series": series, "trade": trade}
        country["outlook"] = outlook.score(country)
        countries.append(country)

    log("commodities ...")
    commodities = []
    for sid, name in config.COMMODITIES.items():
        hist = sources.commodity(sid)
        commodities.append({"id": sid, "name": name, "history": hist,
                            "forecast": model.forecast(hist, config.FORECAST_HORIZON_MONTHS, "M")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "model": model.name,
        "trade_codes": config.TRADE_CODES,
        "weights": config.WEIGHTS,
        "countries": countries,
        "commodities": commodities,
    }, indent=1), encoding="utf-8")
    log(f"wrote {OUT}")
    for c in countries:
        o = c["outlook"]
        log(f"  {c['name']:<15} {o['label']:<12} {o['score']:+4d}  ({o['coverage']})")


if __name__ == "__main__":
    main()
