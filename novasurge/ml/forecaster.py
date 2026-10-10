"""
LSTM telemetry forecaster.

Input : the last LSTM_HISTORY normalised feature vectors of one service (60s)
Output: the next LSTM_HORIZON vectors (the coming 60s)

The network predicts *changes* relative to the last observation (residual
parameterisation), so its prior is "things stay as they are" and it only has to
learn dynamics: mean-reversion after blips, momentum of developing degradations.

Two signals come out of it at inference time:
  * predicted_score_60s — the forecast vector 60s ahead scored by the Isolation
    Forest: "will this service look anomalous in a minute?"
  * one-step residual   — how surprising the newest observation is given the
    forecast made one tick earlier (a temporal anomaly signal).
"""

from __future__ import annotations

import torch
from torch import nn


class TelemetryForecaster(nn.Module):
    def __init__(self, n_features: int, hidden: int = 48, horizon: int = 12):
        super().__init__()
        self.n_features = n_features
        self.hidden = hidden
        self.horizon = horizon
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, horizon * n_features),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: (batch, history, features)
        out, _ = self.lstm(x)
        delta = self.head(out[:, -1, :]).view(-1, self.horizon, self.n_features)
        return x[:, -1:, :] + delta

    def config(self) -> dict:
        return {"n_features": self.n_features, "hidden": self.hidden, "horizon": self.horizon}
