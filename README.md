# Sightline

Early-warning monitor for fenestration (window, door and façade) markets.

Sightline pulls free public data every month, forecasts it with Google's **TimesFM** forecasting model,
and turns it into one outlook score per country, shown on a web dashboard.

Current countries: United Kingdom, India, Brazil, Thailand, Vietnam, Singapore, China.

## What it tracks

| Signal | Why it matters for fenestration | Source |
|---|---|---|
| Real house prices | Rising prices lead new building and renovation | BIS |
| Central bank policy rate | Cheaper credit leads construction starts by 6-18 months | BIS |
| Growth & investment | IMF GDP growth forecasts (3 years ahead) and the investment-to-GDP trend | IMF World Economic Outlook, World Bank |
| Construction growth | Industry (incl. construction) and fixed-investment growth | World Bank |
| Fenestration imports | Direct demand for aluminium frames, PVC windows, hardware, insulating glass | UN Comtrade |
| Input costs | Aluminium, zinc, copper and oil (PVC/energy) prices | FRED (IMF commodity prices) |

No API keys and no company data are needed.

## Outlook score

Each signal is scaled to −1..+1 and weighted (house prices 25%, rates 20%, investment 20%,
construction 15%, imports 20%), then multiplied by 100.
Above +15 = **Expanding**, below −15 = **Contracting**, otherwise **Stable**.
Missing signals are skipped. Weights and thresholds live in [`sightline/config.py`](sightline/config.py).
After changing them, run `python -m sightline.rescore` to recompute scores from the saved data without refetching.

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pip install -r requirements-timesfm.txt   # optional: Google TimesFM (~1 GB with PyTorch + model)

python -m sightline.build                 # fetch data, forecast, score -> web/data/sightline.json
python -m http.server 8000 -d web         # open http://localhost:8000
```

Without TimesFM installed (or with `--no-timesfm`) a simple damped-trend model is used instead.

## Monthly refresh

[`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) reruns the pipeline on the 3rd of
every month and commits the new `web/data/sightline.json`. You can also run it by hand from the
repository's **Actions** tab.

### When a source refuses GitHub's servers

Some sources (the IMF, and FRED's public download) refuse requests from cloud servers. When that happens
the build keeps the last good data for that source, and the dashboard header says which sources were kept.
For fresh commodity prices on GitHub, add a free FRED API key
(https://fred.stlouisfed.org/docs/api/api_key.html) as a repository secret named `FRED_API_KEY`
(Settings → Secrets and variables → Actions). The IMF publishes new forecasts only in April and October.

## Adding a country

Add one line to `COUNTRIES` in [`sightline/config.py`](sightline/config.py) with its ISO codes,
UN Comtrade reporter code and currency, then rerun the build.

## Limits

- Forecasts extend past patterns. They cannot foresee policy changes or shocks.
- For large producers (China), imports are a weaker demand signal than for import-reliant markets.
- Vietnam has no BIS house-price index; Singapore has no policy rate (it manages its exchange rate).
- Trade data lags about a year. HS 7610 (aluminium structures) also includes non-window items such as solar mounting
  frames, so the import signal uses the median growth across the four product groups rather than the total.
