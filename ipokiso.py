import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

URL = "https://www.ipokiso.com/company/index.html"
OUTPUT_FILE = Path(__file__).resolve().parent / "ipokiso.json"

FIELD_NAMES = [
    "overall_rating",
    "market",
    "application_period",
    "listing_date",
    "winning_shares",
    "expected_price",
    "provisional_range",
    "offering_price",
    "initial_price",
    "initial_price_change",
    "target_securities",
]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def get_target_months() -> tuple[int, int]:
    now = datetime.now()
    current_month = now.month
    next_month = 1 if current_month == 12 else current_month + 1
    return current_month, next_month


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


def is_header_row(row: Tag) -> bool:
    return row.find("th") is not None


def parse_company_cell(cell: Tag) -> dict:
    link = cell.find("a", href=True)
    name = normalize_text(link.get_text()) if link else ""
    url = link["href"] if link else ""

    code_match = re.search(r"[（(]([^）)]+)[）)]", cell.get_text("\n", strip=True))
    code = code_match.group(1) if code_match else ""

    year_match = re.search(r"/company/(\d{4})/", url)
    year = year_match.group(1) if year_match else ""

    return {
        "kabu_name": name,
        "code": code,
        "detail_url": url,
        "year": year,
    }


def parse_rating(cell: Tag) -> str:
    img = cell.find("img", alt=True)
    if img and img["alt"]:
        return img["alt"].strip()
    return normalize_text(cell.get_text())


def parse_securities(cell: Tag) -> list[dict]:
    securities = []
    line_nodes: list = []
    for child in cell.children:
        if isinstance(child, Tag) and child.name == "br":
            if line_nodes:
                securities.append(_parse_security_line(line_nodes))
                line_nodes = []
            continue
        line_nodes.append(child)
    if line_nodes:
        securities.append(_parse_security_line(line_nodes))

    return [item for item in securities if item["name"]]


def _parse_security_line(nodes: list) -> dict:
    name = ""
    url = ""
    role = ""

    for node in nodes:
        if isinstance(node, NavigableString):
            continue
        if node.name == "a":
            href = node.get("href", "")
            text = normalize_text(node.get_text())
            if href.startswith("/security/") or node.find("b"):
                name = text
                url = href
            elif node.get("title"):
                role_match = re.search(r"[（(]([^）)]+)[）)]", text)
                if role_match:
                    role = role_match.group(1)
        elif node.name == "b":
            name = normalize_text(node.get_text())

    return {"name": name, "url": url, "role": role}


def parse_detail_row(cells: list[Tag]) -> dict:
    values = [normalize_text(cell.get_text("\n", strip=True)) for cell in cells]
    item = dict(zip(FIELD_NAMES, values))
    item["overall_rating"] = parse_rating(cells[0])
    item["target_securities"] = parse_securities(cells[-1])
    return item


def parse_month_section(section: Tag, month: int) -> list[dict]:
    table_head = section.select_one(".tableHead table.sche")
    table_body = section.select_one(".tableBody table.sche")
    if not table_head or not table_body:
        return []

    companies = []
    for row in table_head.find_all("tr"):
        if is_header_row(row):
            continue
        cell = row.find("td")
        if cell:
            companies.append(parse_company_cell(cell))

    details = []
    for row in table_body.find_all("tr"):
        if is_header_row(row):
            continue
        cells = row.find_all("td")
        if cells:
            details.append(parse_detail_row(cells))

    if len(companies) != len(details):
        raise ValueError(
            f"month {month}: company count ({len(companies)}) "
            f"!= detail count ({len(details)})"
        )

    items = []
    for company, detail in zip(companies, details):
        items.append({"month": month, **company, **detail})
    return items


def scrape_months(months: list[int], html: str | None = None) -> dict:
    page_html = html or fetch_html()
    soup = BeautifulSoup(page_html, "html.parser")

    result = {
        "source": URL,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "months": months,
        "items": [],
    }

    for month in months:
        section = soup.find("div", id=f"m{month}")
        if section is None:
            print(f"month {month}: section not found, skipped")
            continue

        heading = section.find("h2")
        month_label = normalize_text(heading.get_text()) if heading else f"{month}月"
        items = parse_month_section(section, month)
        print(f"{month_label}: {len(items)} companies")
        result["items"].extend(items)

    result["total"] = len(result["items"])
    return result


def main() -> None:
    current_month, next_month = get_target_months()
    months = [current_month, next_month]
    print(f"Scraping months: {months}")

    result = scrape_months(months)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {result['total']} items to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
