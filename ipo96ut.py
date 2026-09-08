import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

URL = "https://96ut.com/ipo/"
OUTPUT_FILE = Path(__file__).resolve().parent / "ipo96ut.json"
TABLE_TITLE = "直近・今後上場予定のIPO一覧"

HEADER_MAP = {
    "上場日": "listing_date",
    "code": "code",
    "銘柄名": "kabu_name",
    "市場": "market",
    "想定価格": "expected_price",
    "仮条件": "provisional_range",
    "評価": "rating",
    "公募": "offering_price",
    "初値": "initial_price",
    "予想": "forecast_price",
    "投票": "vote",
    "ステータス": "status",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fetch_html(url: str = URL, timeout: int = 30) -> str:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def find_upcoming_table(soup: BeautifulSoup) -> Tag:
    heading = soup.find(
        "h3",
        class_="title-header",
        string=lambda text: text and TABLE_TITLE in normalize_text(text),
    )
    if heading is None:
        raise ValueError(f"section not found: {TABLE_TITLE}")

    table_wrap = heading.find_next("div", class_="tablewrap")
    if table_wrap is None:
        raise ValueError("table container not found")

    table = table_wrap.find("table")
    if table is None:
        raise ValueError("table not found")
    return table


def get_cell_text(cell: Tag) -> str:
    return normalize_text(cell.get_text(" ", strip=True))


def parse_cell(field: str, cell: Tag) -> dict:
    text = get_cell_text(cell)
    link = cell.find("a", href=True)

    if field == "code":
        return {
            "code": text,
            "yahoo_url": link["href"] if link else "",
        }
    if field == "kabu_name":
        ipo_id = ""
        if link:
            match = re.search(r"/article/ipo/(\d+)/?", link["href"])
            if match:
                ipo_id = match.group(1)
        return {
            "kabu_name": text,
            "detail_url": link["href"] if link else "",
            "ipo_id": ipo_id,
        }
    if field == "forecast_price":
        return {
            "forecast_price": text.replace(",", ""),
            "forecast_url": link["href"] if link else "",
        }
    if field == "vote":
        vote_url = link["href"] if link else ""
        ipo_id = ""
        if vote_url:
            match = re.search(r"ipo_id=(\d+)", vote_url)
            if match:
                ipo_id = match.group(1)
        return {
            "vote": text,
            "vote_url": vote_url,
            "ipo_id": ipo_id or None,
        }

    value = text.replace(",", "") if field in {
        "expected_price",
        "offering_price",
        "initial_price",
    } else text
    return {field: value or "-"}


def parse_row(cells: list[Tag], field_names: list[str]) -> dict:
    item: dict = {}
    for field, cell in zip(field_names, cells):
        item.update(parse_cell(field, cell))

    if not item.get("ipo_id"):
        detail_url = item.get("detail_url", "")
        match = re.search(r"/article/ipo/(\d+)/?", detail_url)
        if match:
            item["ipo_id"] = match.group(1)

    return item


def scrape(html: str | None = None) -> dict:
    page_html = html or fetch_html()
    soup = BeautifulSoup(page_html, "html.parser")
    table = find_upcoming_table(soup)

    header_row = table.find("tr")
    if header_row is None:
        raise ValueError("table header not found")

    field_names = [
        HEADER_MAP.get(get_cell_text(th), get_cell_text(th))
        for th in header_row.find_all("th")
    ]

    items = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        if len(cells) != len(field_names):
            raise ValueError(
                f"expected {len(field_names)} cells, got {len(cells)}"
            )
        items.append(parse_row(cells, field_names))

    return {
        "source": URL,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(items),
        "items": items,
    }


def main() -> None:
    result = scrape()
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {result['total']} items to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
