from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

WIDTH = 1200
HEIGHT = 350
LEFT = 36
RIGHT = 36
TOP = 30
BOTTOM = 52
MAX_DAYS = 90
UP = "#E85B55"
DOWN = "#67C49A"
BACKGROUND = "#0D1117"
MUTED = "#8B949E"
AXIS = "#30363D"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
    return parser.parse_args()


def read_days(source: Path) -> list[dict[str, Any]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_days = payload.get("klines")
    if not isinstance(raw_days, list):
        raise ValueError("Source data must contain a klines list.")
    by_date: dict[date, dict[str, Any]] = {}
    for raw_day in raw_days:
        if not isinstance(raw_day, dict):
            continue
        try:
            current_date = date.fromisoformat(str(raw_day["date"]))
            day = {
                "date": current_date,
                "open": float(raw_day["open"]),
                "high": float(raw_day["high"]),
                "low": float(raw_day["low"]),
                "close": float(raw_day["close"]),
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Every K-line needs valid date and OHLC values.") from error
        if day["high"] < max(day["open"], day["close"]):
            raise ValueError("High cannot be below open or close.")
        if day["low"] > min(day["open"], day["close"]):
            raise ValueError("Low cannot be above open or close.")
        by_date[current_date] = day
    return [by_date[item_date] for item_date in sorted(by_date)]


def select_window(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not days:
        raise ValueError("No K-line data is available to export.")
    start_date = days[-1]["date"] - timedelta(days=MAX_DAYS - 1)
    return [day for day in days if day["date"] >= start_date]


def y_position(value: float, minimum: float, maximum: float) -> float:
    return TOP + (maximum - value) / (maximum - minimum) * (HEIGHT - TOP - BOTTOM)


def x_position(index: int, count: int) -> float:
    if count <= 1:
        return WIDTH / 2
    return LEFT + index / (count - 1) * (WIDTH - LEFT - RIGHT)


def value_label(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def tick_indexes(count: int) -> list[int]:
    if count <= 1:
        return [0]
    total = min(6, count)
    return sorted({round(index * (count - 1) / (total - 1)) for index in range(total)})

def annotation(label: str, value: float, x: float, y: float, high: bool) -> list[str]:
    direction = -1 if high else 1
    vertical_end = y + direction * 12
    use_left = x > WIDTH * 0.62
    horizontal_end = x - 56 if use_left else x + 56
    anchor = "end" if use_left else "start"
    text_x = horizontal_end - 5 if use_left else horizontal_end + 5
    text_y = vertical_end - 4 if high else vertical_end + 15
    if high:
        text_y = max(text_y, TOP + 14)
    else:
        text_y = min(text_y, HEIGHT - BOTTOM - 8)
    return [
        f'<path d="M {x:.2f} {y:.2f} V {vertical_end:.2f} H {horizontal_end:.2f}" fill="none" stroke="{MUTED}" stroke-width="1.25" stroke-linecap="round"/>',
        f'<text x="{text_x:.2f}" y="{text_y:.2f}" fill="{MUTED}" font-family="ui-monospace, Consolas, monospace" font-size="13" text-anchor="{anchor}">{label} {value_label(value)}</text>',
    ]


def chart_svg(days: list[dict[str, Any]]) -> str:
    low = min(day["low"] for day in days)
    high = max(day["high"] for day in days)
    padding = max((high - low) * 0.08, 1.0)
    minimum, maximum = low - padding, high + padding
    plot_width = WIDTH - LEFT - RIGHT
    body_width = max(4.0, min(10.0, plot_width / max(len(days), 1) * 0.58))
    axis_y = HEIGHT - BOTTOM + 10
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Life K-line chart">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="{BACKGROUND}"/>',
        f'<line x1="{LEFT}" y1="{axis_y}" x2="{WIDTH - RIGHT}" y2="{axis_y}" stroke="{AXIS}" stroke-width="1"/>',
    ]
    high_index = max(range(len(days)), key=lambda index: days[index]["high"])
    low_index = min(range(len(days)), key=lambda index: days[index]["low"])
    for index, day in enumerate(days):
        x = x_position(index, len(days))
        color = UP if day["close"] >= day["open"] else DOWN
        y_high = y_position(day["high"], minimum, maximum)
        y_low = y_position(day["low"], minimum, maximum)
        y_open = y_position(day["open"], minimum, maximum)
        y_close = y_position(day["close"], minimum, maximum)
        body_top = min(y_open, y_close)
        body_height = max(abs(y_open - y_close), 3.0)
        parts.append(f'<line x1="{x:.2f}" y1="{y_high:.2f}" x2="{x:.2f}" y2="{y_low:.2f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
        parts.append(f'<rect x="{x - body_width / 2:.2f}" y="{body_top:.2f}" width="{body_width:.2f}" height="{body_height:.2f}" rx="1.5" fill="{color}"/>')
    for index in tick_indexes(len(days)):
        x = x_position(index, len(days))
        parts.append(f'<line x1="{x:.2f}" y1="{axis_y}" x2="{x:.2f}" y2="{axis_y + 5}" stroke="{AXIS}" stroke-width="1"/>')
        parts.append(f'<text x="{x:.2f}" y="{axis_y + 25}" fill="{MUTED}" font-family="ui-monospace, Consolas, monospace" font-size="12" text-anchor="middle">{days[index]["date"].strftime("%m/%d")}</text>')
    high_day, low_day = days[high_index], days[low_index]
    parts.extend(annotation("\u524d\u9ad8", high_day["high"], x_position(high_index, len(days)), y_position(high_day["high"], minimum, maximum), True))
    parts.extend(annotation("\u524d\u4f4e", low_day["low"], x_position(low_index, len(days)), y_position(low_day["low"], minimum, maximum), False))
    return "\n".join(parts + ['</svg>', ''])


def title_svg() -> str:
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 108" role="img" aria-label="What if life could be quantified with OHLC?">',
        '<text x="600" y="46" fill="#E6EDF3" font-family="Georgia, Times New Roman, serif" font-size="31" font-weight="500" text-anchor="middle" letter-spacing="0.5">WHAT IF LIFE COULD BE QUANTIFIED WITH <tspan font-weight="700" font-style="italic">OHLC</tspan>?</text>',
        '<text x="600" y="79" fill="#8B949E" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="17" text-anchor="middle">\u5982\u679c\u4eba\u751f\u53ef\u4ee5\u7528 OHLC \u91cf\u5316\uff0c\u90a3\u4f1a\u662f\u4ec0\u4e48\u6837\u5b50\u5462\u2026\u2026</text>',
        '</svg>',
        '',
    ])


def public_days(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"date": day["date"].isoformat(), "open": day["open"], "high": day["high"], "low": day["low"], "close": day["close"]} for day in days]


def main() -> None:
    options = args()
    days = select_window(read_days(options.source))
    options.output_dir.mkdir(parents=True, exist_ok=True)
    (options.output_dir / "life-kline.json").write_text(json.dumps(public_days(days), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (options.output_dir / "life-kline.svg").write_text(chart_svg(days), encoding="utf-8")
    (options.output_dir / "life-kline-title.svg").write_text(title_svg(), encoding="utf-8")
    print(f"Exported {len(days)} daily K-lines.")


if __name__ == "__main__":
    main()
