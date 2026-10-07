"""Feature engineering for the forecasting models.

Leakage rule enforced throughout this module: every feature describing the
past is produced with ``shift(1)`` before any rolling statistic is taken, so a
row for day *t* can only ever contain information available at the end of day
*t-1*. Calendar features are exempt because a future date is genuinely known
in advance.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LAGS = (1, 2, 3, 7, 14, 28)
ROLLING_WINDOWS = (7, 14, 28)


def add_calendar_features(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    """Add date derived features. These are known ahead of time."""
    frame = frame.copy()
    dates = pd.to_datetime(frame[date_column])

    frame["day_of_week"] = dates.dt.dayofweek
    frame["day_of_month"] = dates.dt.day
    frame["day_of_year"] = dates.dt.dayofyear
    frame["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    frame["month"] = dates.dt.month
    frame["quarter"] = dates.dt.quarter
    frame["year"] = dates.dt.year
    frame["is_weekend"] = (frame["day_of_week"] >= 5).astype(int)
    frame["is_month_start"] = dates.dt.is_month_start.astype(int)
    frame["is_month_end"] = dates.dt.is_month_end.astype(int)

    # Cyclical encodings so the model understands that December is next to January.
    frame["day_of_week_sin"] = np.sin(2 * np.pi * frame["day_of_week"] / 7)
    frame["day_of_week_cos"] = np.cos(2 * np.pi * frame["day_of_week"] / 7)
    frame["month_sin"] = np.sin(2 * np.pi * frame["month"] / 12)
    frame["month_cos"] = np.cos(2 * np.pi * frame["month"] / 12)
    frame["day_of_year_sin"] = np.sin(2 * np.pi * frame["day_of_year"] / 365.25)
    frame["day_of_year_cos"] = np.cos(2 * np.pi * frame["day_of_year"] / 365.25)

    # Linear time index lets tree models express a long term trend.
    frame["time_index"] = (dates - dates.min()).dt.days
    return frame


def add_lag_features(
    frame: pd.DataFrame,
    target: str,
    *,
    group_column: str | None = None,
    lags: Tuple[int, ...] = LAGS,
    windows: Tuple[int, ...] = ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Add lagged and rolling statistics computed strictly from past values."""
    frame = frame.copy()

    if group_column:
        grouped = frame.groupby(group_column)[target]
    else:
        grouped = frame[target]

    for lag in lags:
        frame[f"{target}_lag_{lag}"] = (
            grouped.shift(lag) if group_column else frame[target].shift(lag)
        )

    # Shift first, then roll: the window can never include the current day.
    shifted = grouped.shift(1) if group_column else frame[target].shift(1)
    if group_column:
        shifted_by_group = shifted.groupby(frame[group_column])
        for window in windows:
            frame[f"{target}_roll_mean_{window}"] = shifted_by_group.transform(
                lambda series, w=window: series.rolling(w, min_periods=max(2, w // 3)).mean()
            )
            frame[f"{target}_roll_std_{window}"] = shifted_by_group.transform(
                lambda series, w=window: series.rolling(w, min_periods=max(2, w // 3)).std()
            )
            frame[f"{target}_roll_max_{window}"] = shifted_by_group.transform(
                lambda series, w=window: series.rolling(w, min_periods=max(2, w // 3)).max()
            )
    else:
        for window in windows:
            frame[f"{target}_roll_mean_{window}"] = shifted.rolling(
                window, min_periods=max(2, window // 3)
            ).mean()
            frame[f"{target}_roll_std_{window}"] = shifted.rolling(
                window, min_periods=max(2, window // 3)
            ).std()
            frame[f"{target}_roll_max_{window}"] = shifted.rolling(
                window, min_periods=max(2, window // 3)
            ).max()

    # Short versus medium term momentum.
    short, long = f"{target}_roll_mean_7", f"{target}_roll_mean_28"
    if short in frame and long in frame:
        frame["momentum_ratio"] = frame[short] / frame[long].replace(0, np.nan)

    return frame


def build_sales_features(daily_sales: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Feature matrix for the business level revenue model."""
    frame = daily_sales.sort_values("date").reset_index(drop=True)
    frame = add_calendar_features(frame)
    frame = add_lag_features(frame, "revenue")
    frame = add_lag_features(frame, "transactions", lags=(1, 7), windows=(7,))

    feature_columns = [
        column
        for column in frame.columns
        if column not in {"date", "revenue", "transactions", "units", "discount"}
    ]

    # Rows without a full lag history cannot be used for supervised learning.
    frame = frame.dropna(subset=feature_columns).reset_index(drop=True)
    logger.info(
        "Sales feature matrix: %s rows x %s features", len(frame), len(feature_columns)
    )
    return frame, feature_columns


def build_demand_features(
    product_demand: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """Feature matrix for the product level demand model."""
    frame = product_demand.sort_values(["product_id", "date"]).reset_index(drop=True)
    frame = add_calendar_features(frame)
    frame = add_lag_features(frame, "units", group_column="product_id")

    # Product context: price position and how the product ranks overall.
    frame["price_ratio"] = frame["avg_price"] / frame["selling_price"].replace(0, np.nan)
    frame["price_ratio"] = frame["price_ratio"].fillna(1.0)
    frame["margin_percent"] = (
        (frame["selling_price"] - frame["cost_price"])
        / frame["selling_price"].replace(0, np.nan)
    ).fillna(0.0)

    # Category demand on the previous day, again strictly backward looking.
    category_daily = (
        frame.groupby(["category", "date"])["units"].transform("sum")
    )
    frame["category_units_same_day"] = category_daily
    frame["category_units_lag_1"] = (
        frame.groupby("product_id")["category_units_same_day"].shift(1)
    )
    frame = frame.drop(columns=["category_units_same_day"])

    frame["category_code"] = frame["category"].astype("category").cat.codes

    exclude = {
        "date",
        "units",
        "revenue",
        "product_id",
        "category",
        "cost_price",
    }
    feature_columns = [column for column in frame.columns if column not in exclude]

    frame = frame.dropna(subset=feature_columns).reset_index(drop=True)
    logger.info(
        "Demand feature matrix: %s rows x %s features (%s products)",
        len(frame),
        len(feature_columns),
        frame["product_id"].nunique(),
    )
    return frame, feature_columns


def chronological_split(
    frame: pd.DataFrame,
    *,
    test_days: int = 60,
    validation_days: int = 60,
    date_column: str = "date",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by time, never at random.

    Random splitting on time series data leaks the future into training and
    produces impressive but meaningless scores.
    """
    frame = frame.sort_values(date_column)
    last_date = frame[date_column].max()

    test_start = last_date - pd.Timedelta(days=test_days - 1)
    validation_start = test_start - pd.Timedelta(days=validation_days)

    train = frame[frame[date_column] < validation_start]
    validation = frame[
        (frame[date_column] >= validation_start) & (frame[date_column] < test_start)
    ]
    test = frame[frame[date_column] >= test_start]

    logger.info(
        "Chronological split -> train %s (to %s) | validation %s | test %s (from %s)",
        len(train),
        validation_start.date() if len(train) else "n/a",
        len(validation),
        len(test),
        test_start.date(),
    )
    return train, validation, test
