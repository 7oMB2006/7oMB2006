\
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

CHART_WIDTH = 1200
CHART_HEIGHT = 320
PADDING_X = 28
PADDING_Y = 24
MAX_WINDOW_DAYS = 90
UP_COLOR = "#E85B55"
DOWN_COLOR = "#67C49A"
BACKGROUND = "#0D1117"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a privacy-safe life K-line image for a GitHub profile."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets",
    )
    return parser.parse_args()


def read_klines(source: Path) -> list[dict[str, Any]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_klines = payload.get("klines")
    if not isinstance(raw_klines, list):
        raise ValueError("Source data must contain a klines list.")

    by_date: dict[date, dict[str, Any]] = {}
    for raw_kline in raw_klines:
        if not isinstance(raw_kline, dict):
            continue
        try:
            current_date = date.fromisoformat(str(raw_kline["date"]))
            kline = {
                "date": current_date,
                "open": float(raw_kline["open"]),
                "high": float(raw_kline["high"]),
                "low": float(raw_kline["low"]),
                "close": float(raw_kline["close"]),
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Each K-line must have valid date and OHLC values.") from error
        if kline["high"] < max(kline["open"], kline["close"]):
            raise ValueError("K-line high cannot be below open or close.")
        if kline["low"] > min(kline["open"], kline["close"]):
            raise ValueError("K-line low cannot be above open or close.")
        by_date[current_date] = kline

    return [by_date[current_date] for current_date in sorted(by_date)]


def select_window(klines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], date, date]:
    if not klines:
        raise ValueError("No K-line data is available to export.")

    end_date = klines[-1]["date"]
    first_date = klines[0]["date"]
    if (end_date - first_date).days >= MAX_WINDOW_DAYS - 1:
        start_date = end_date - timedelta(days=MAX_WINDOW_DAYS - 1)
        return [kline for kline in klines if kline["date"] >= start_date], start_date, end_date

    return klines, first_date, end_date


def scale_y(value: float, minimum: float, maximum: float) -> float:
    plot_height = CHART_HEIGHT - PADDING_Y * 2
    return PADDING_Y + (maximum - value) / (maximum - minimum) * plot_height


def position_x(current: date, start: date, end: date, count: int) -> float:
    plot_width = CHART_WIDTH - PADDING_X * 2
    span_days = (end - start).days
    if span_days == 0 or count == 1:
        return CHART_WIDTH / 2
    return PADDING_X + (current - start).days / span_days * plot_width


def build_svg(klines: list[dict[str, Any]], start_date: date, end_date: date) -> str:
    lowest = min(kline["low"] for kline in klines)
    highest = max(kline["high"] for kline in klines)
    padding = max((highest - lowest) * 0.08, 1.0)
    minimum = lowest - padding
    maximum = highest + padding
    plot_width = CHART_WIDTH - PADDING_X * 2
    visible_days = max((end_date - start_date).days + 1, len(klines))
    candle_width = max(3.0, min(10.0, plot_width / visible_days * 0.56))

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" aria-label="Life K-line chart">',
        f'<rect width="{CHART_WIDTH}" height="{CHART_HEIGHT}" rx="18" fill="{BACKGROUND}"/>',
    ]
    for kline in klines:
        x = position_x(kline["date"], start_date, end_date, len(klines))
        color = UP_COLOR if kline["close"] >= kline["open"] else DOWN_COLOR
        y_high = scale_y(kline["high"], minimum, maximum)
        y_low = scale_y(kline["low"], minimum, maximum)
        y_open = scale_y(kline["open"], minimum, maximum)
        y_close = scale_y(kline["close"], minimum, maximum)
        body_top = min(y_open, y_close)
        body_height = max(abs(y_open - y_close), 3.0)
        elements.append(
            f'<line x1="{x:.2f}" y1="{y_high:.2f}" x2="{x:.2f}" y2="{y_low:.2f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        )
        elements.append(
            f'<rect x="{x - candle_width / 2:.2f}" y="{body_top:.2f}" width="{candle_width:.2f}" height="{body_height:.2f}" rx="1.5" fill="{color}"/>'
        )
    elements.append('</svg>')
    return "\n".join(elements) + "\n"


def export_public_data(klines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "date": kline["date"].isoformat(),
            "open": kline["open"],
            "high": kline["high"],
            "low": kline["low"],
            "close": kline["close"],
        }
        for kline in klines
    ]


def main() -> None:
    args = parse_args()
    klines = read_klines(args.source)
    selected, start_date, end_date = select_window(klines)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "life-kline.json").write_text(
        json.dumps(export_public_data(selected), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "life-kline.svg").write_text(
        build_svg(selected, start_date, end_date), encoding="utf-8"
    )
    print(f"Exported {len(selected)} daily K-lines.")


if __name__ == "__main__":
    main()
