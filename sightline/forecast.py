"""Forecasting: Google's TimesFM when installed, a damped-trend model otherwise.

Both return, for each future period, a point forecast plus an 80% band (10th-90th percentile).
TimesFM is used zero-shot: it was pre-trained on billions of time points and needs no training here.
"""

from __future__ import annotations

import math

import numpy as np


def _next_periods(last: str, n: int, freq: str) -> list[str]:
    """'2026-09' -> ['2026-10', ...] or '2026-Q2' -> ['2026-Q3', ...]."""
    year = int(last[:4])
    out = []
    if freq == "Q":
        q = int(last[-1])
        for _ in range(n):
            q += 1
            if q > 4:
                q, year = 1, year + 1
            out.append(f"{year}-Q{q}")
    else:
        m = int(last[5:7])
        for _ in range(n):
            m += 1
            if m > 12:
                m, year = 1, year + 1
            out.append(f"{year}-{m:02d}")
    return out


class Forecaster:
    def __init__(self, use_timesfm: bool = True):
        self._tfm = None
        self._api = None
        self.name = "Damped trend (fallback)"
        if use_timesfm:
            self._load_timesfm()

    # ---------- TimesFM ----------

    def _load_timesfm(self) -> None:
        try:
            import timesfm  # noqa: F401
        except Exception as exc:  # not installed: stay on fallback
            print(f"[sightline] TimesFM not available ({exc.__class__.__name__}); using fallback model")
            return
        import timesfm

        if hasattr(timesfm, "TimesFM_2p5_200M_torch"):  # timesfm >= 2.5
            import torch
            torch.set_float32_matmul_precision("high")
            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
            model.compile(timesfm.ForecastConfig(
                max_context=512, max_horizon=64, normalize_inputs=True,
                use_continuous_quantile_head=True, force_flip_invariance=True,
                infer_is_positive=True, fix_quantile_crossing=True,
            ))
            self._tfm, self._api, self.name = model, "2.5", "Google TimesFM 2.5 (200M)"
        else:  # timesfm 1.x package, TimesFM 2.0 checkpoint
            model = timesfm.TimesFm(
                hparams=timesfm.TimesFmHparams(backend="cpu", per_core_batch_size=32, horizon_len=64,
                                               num_layers=50, use_positional_embedding=False, context_len=512),
                checkpoint=timesfm.TimesFmCheckpoint(huggingface_repo_id="google/timesfm-2.0-500m-pytorch"),
            )
            self._tfm, self._api, self.name = model, "2.0", "Google TimesFM 2.0 (500M)"

    def _timesfm(self, values: np.ndarray, horizon: int, freq: str):
        if self._api == "2.5":
            point, quant = self._tfm.forecast(horizon=horizon, inputs=[values])
        else:
            point, quant = self._tfm.forecast([values], freq=[0 if freq == "M" else 1])
        point, quant = np.asarray(point)[0][:horizon], np.asarray(quant)[0][:horizon]
        # quantile layout: [mean, q10, q20, ..., q90]
        return point, quant[:, 1], quant[:, -1]

    # ---------- fallback: damped Holt ----------

    @staticmethod
    def _damped(values: np.ndarray, horizon: int):
        y = values[-120:]
        best = None
        for a in (0.2, 0.4, 0.6, 0.8, 0.95):
            for b in (0.05, 0.1, 0.2, 0.3):
                lvl, tr, phi, sse, res = y[0], y[1] - y[0] if len(y) > 1 else 0.0, 0.9, 0.0, []
                for t in range(1, len(y)):
                    pred = lvl + phi * tr
                    err = y[t] - pred
                    res.append(err)
                    sse += err * err
                    new_lvl = a * y[t] + (1 - a) * pred
                    tr = b * (new_lvl - lvl) + (1 - b) * phi * tr
                    lvl = new_lvl
                if best is None or sse < best[0]:
                    best = (sse, lvl, tr, np.std(res) if res else 0.0)
        _, lvl, tr, sd = best
        phi = 0.9
        point, lo, hi, damp = [], [], [], 0.0
        for h in range(1, horizon + 1):
            damp += phi ** h
            p = lvl + damp * tr
            w = 1.28 * sd * math.sqrt(h)
            point.append(p)
            lo.append(p - w)
            hi.append(p + w)
        return np.array(point), np.array(lo), np.array(hi)

    # ---------- public ----------

    def forecast(self, history: list[dict], horizon: int, freq: str) -> list[dict]:
        if len(history) < 8:
            return []
        values = np.array([p["value"] for p in history], dtype=float)
        if self._tfm is not None:
            point, lo, hi = self._timesfm(values, horizon, freq)
        else:
            point, lo, hi = self._damped(values, horizon)
        dates = _next_periods(history[-1]["date"], horizon, freq)
        return [{"date": d, "value": round(float(p), 4), "lo": round(float(l), 4), "hi": round(float(h), 4)}
                for d, p, l, h in zip(dates, point, lo, hi)]
