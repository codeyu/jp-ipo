import argparse
import json
import re
import time
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://96ut.com/ipo/data.php?year=all&k=1&m=1&s=1&t=all&page={page}"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "ipo_data.json"
START_PAGE = 1
END_PAGE = 26

HEADER_FIELD_NAMES = {
    "市場 [code]": "marketCode",
    "銘柄名": "stockName",
    "上場日": "listingDate",
    "主幹事": "leadUnderwriter",
    "想定 (仮条件)": "expectedPriceRange",
    "公募": "publicOfferingPrice",
    "吸収金額": "absorptionAmount",
    "評価": "rating",
    "初値": "initialPrice",
    "(上昇率) 損益": "initialReturnProfit",
    "現在値 (差分)": "currentPriceDifference",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def get_cell_text(cell) -> str:
    return normalize_text(cell.get_text(" ", strip=True))


def parse_page(html: str, page: int) -> Dict[str, List[Dict[str, str]]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("div.tablewrap table.kuro")
    if table is None:
        raise ValueError(f"page {page}: table not found")

    header_cells = table.select("tr th")
    headers = [get_cell_text(th) for th in header_cells]
    field_names = [HEADER_FIELD_NAMES.get(header, to_camel_case(header)) for header in headers]
    columns = [
        {
            "name": field_name,
            "showName": header,
        }
        for field_name, header in zip(field_names, headers)
    ]

    items = []
    for row in table.select("tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        if len(cells) != len(field_names):
            raise ValueError(f"page {page}: expected {len(field_names)} cells, got {len(cells)}")

        item = {
            field_name: get_cell_text(cell)
            for field_name, cell in zip(field_names, cells)
        }
        items.append(item)

    return {
        "columns": columns,
        "items": items,
    }


def to_camel_case(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        return "field"

    first, *rest = [word.lower() for word in words]
    return first + "".join(word.capitalize() for word in rest)


def fetch_page(session: requests.Session, page: int, timeout: int) -> str:
    response = session.get(BASE_URL.format(page=page), timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def scrape(start_page: int, end_page: int, timeout: int, delay: float) -> Dict[str, object]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )

    all_items = []
    columns = None
    for page in range(start_page, end_page + 1):
        html = fetch_page(session, page, timeout)
        parsed = parse_page(html, page)

        if columns is None:
            columns = parsed["columns"]
        elif columns != parsed["columns"]:
            raise ValueError(f"page {page}: table headers changed")

        all_items.extend(parsed["items"])
        print(f"page {page}: {len(parsed['items'])} items")

        if page < end_page and delay > 0:
            time.sleep(delay)

    return {
        "source": {
            "url": BASE_URL,
            "startPage": start_page,
            "endPage": end_page,
        },
        "columns": columns or [],
        "total": len(all_items),
        "items": all_items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape 96ut IPO result data.")
    parser.add_argument("--start-page", type=int, default=START_PAGE)
    parser.add_argument("--end-page", type=int, default=END_PAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = scrape(args.start_page, args.end_page, args.timeout, args.delay)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved {result['total']} items to {args.output}")


if __name__ == "__main__":
    main()