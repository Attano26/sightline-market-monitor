"""Countries, data series and scoring weights for Sightline.

Add a country by adding one entry to COUNTRIES. Codes:
  iso2      - BIS (policy rate, house prices, FX)
  iso3      - World Bank and IMF
  comtrade  - UN Comtrade numeric reporter code
  currency  - local currency against USD (BIS exchange rates)
"""

COUNTRIES = [
    {"name": "United Kingdom", "iso2": "GB", "iso3": "GBR", "comtrade": 826, "currency": "GBP"},
    {"name": "India",          "iso2": "IN", "iso3": "IND", "comtrade": 699, "currency": "INR"},
    {"name": "Brazil",         "iso2": "BR", "iso3": "BRA", "comtrade": 76,  "currency": "BRL"},
    {"name": "Thailand",       "iso2": "TH", "iso3": "THA", "comtrade": 764, "currency": "THB"},
    {"name": "Vietnam",        "iso2": "VN", "iso3": "VNM", "comtrade": 704, "currency": "VND"},
    {"name": "Singapore",      "iso2": "SG", "iso3": "SGP", "comtrade": 702, "currency": "SGD"},
    {"name": "China",          "iso2": "CN", "iso3": "CHN", "comtrade": 156, "currency": "CNY"},
]

# Harmonised System product codes that stand in for fenestration demand.
TRADE_CODES = {
    "7610":   "Aluminium structures (incl. window & door frames)",
    "392520": "Plastic (PVC) doors, windows and frames",
    "830241": "Window & door hardware (fittings for buildings)",
    "7008":   "Insulating glass units",
}

# Global input costs (monthly, FRED / IMF primary commodity prices, USD per tonne or barrel).
COMMODITIES = {
    "PALUMUSDM":   "Aluminium",
    "PZINCUSDM":   "Zinc (die-cast handles & hardware)",
    "PCOPPUSDM":   "Copper",
    "POILBREUSDM": "Brent crude (PVC & energy costs)",
}

# Annual World Bank indicators.
WORLD_BANK = {
    "NV.IND.TOTL.KD.ZG": "Industry incl. construction, real growth %",
    "NE.GDI.FTOT.KD.ZG": "Gross fixed capital formation, real growth %",
    "SP.URB.GROW":       "Urban population growth %",
}

# IMF World Economic Outlook series (history + forecasts ~5 years ahead).
IMF = {
    "NGDP_RPCH": "Real GDP growth %",
    "NID_NGDP":  "Total investment, % of GDP",
}

FORECAST_HORIZON_MONTHS = 12
HISTORY_START_YEAR = 2010

# Outlook score: each signal is scaled to -1..+1, then weighted. See sightline/outlook.py.
WEIGHTS = {
    "house_prices": 0.25,   # real residential property prices, YoY + forecast direction
    "rates":        0.20,   # policy rate change (falling = supportive)
    "investment":   0.20,   # IMF investment ratio trend + GDP growth outlook
    "construction": 0.15,   # World Bank industry/construction + fixed capital formation growth
    "imports":      0.20,   # fenestration product imports momentum
}
EXPANDING_ABOVE = 15
CONTRACTING_BELOW = -15
