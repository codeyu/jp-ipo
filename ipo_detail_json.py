"""Shared HTML-based detail extraction. Original cells remain available for auditing."""
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import Tag


def text(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def measurement(raw, unit=None, estimated=None):
    normalized = unicodedata.normalize("NFKC", raw).replace(",", "")
    match = re.match(r"\s*([△▲−-]?\d+(?:\.\d+)?)", normalized)
    value = None
    if match:
        number = match[1].replace("△", "-").replace("▲", "-").replace("−", "-")
        value = float(number) if "." in number else int(number)
    return {"value": value, "unit": unit, "raw": raw, "estimated": estimated}


def cell_data(cell, url):
    # Descendant tables have their own records; never flatten their text here.
    strings = [str(s).strip() for s in cell.find_all(string=True)
               if s.find_parent(["td", "th"]) is cell and str(s).strip()]
    return {
        "text": " ".join(strings),
        "links": [{"text": text(a), "url": urljoin(url, a['href'])}
                  for a in cell.find_all("a", href=True)
                  if a.find_parent(["td", "th"]) is cell],
        "images": [{"alt": img.get("alt", ""), "url": urljoin(url, img.get("src", ""))}
                   for img in cell.find_all("img")],
        "italic": any(t.name in ("i", "em") or re.search(
            r"font-style\s*:\s*(italic|oblique)", t.get("style", ""), re.I)
            for t in [cell, *cell.find_all(True)]),
        "rowspan": cell.get("rowspan", "1"), "colspan": cell.get("colspan", "1"),
    }


def extract_details(root, url, source, code, markdown):
    result = {"schema_version": 1, "code": str(code) if code else None,
              "source": source, "detail_url": url,
              "scraped_at": datetime.now(timezone.utc).isoformat(),
              "company": {}, "business": {}, "schedule": {}, "offering": {},
              "pricing": {}, "valuation": {}, "underwriters": [],
              "subscription_brokers": [], "financials": [], "shareholders": [],
              "stock_options": [], "analysis": [], "reader_forecasts": [],
              "documents": [], "content": {"markdown": markdown, "sections": []},
              "raw_tables": [], "warnings": []}
    # Keep every section including commentary and footnotes, in source order.
    section = {"title": "", "markdown": ""}
    for line in markdown.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            if section["markdown"].strip() or section["title"]:
                result["content"]["sections"].append(section)
            section = {"title": heading[2], "markdown": ""}
        else:
            section["markdown"] += line + "\n"
    result["content"]["sections"].append(section)
    for s in result["content"]["sections"]:
        s["markdown"] = s["markdown"].strip()
        if re.search(r"コメント|第一印象|スタンス|評価|初値予想", s["title"]):
            result["analysis"].append(s.copy())
        if re.search(r"みんな|読者", s["title"]):
            result["reader_forecasts"].append(s.copy())
    result["business"]["sections"] = [s.copy() for s in result["content"]["sections"]
                                          if re.search(r"概要|コメント", s["title"])]

    mappings = {
        "会社名": ("company", "name", None), "所在地": ("company", "address", None),
        "会社URL": ("company", "website", None), "設立": ("company", "established", None),
        "会社設立": ("company", "established", None), "従業員数": ("company", "employees", "people"),
        "監査法人": ("company", "auditor", None),
        "想定価格": ("pricing", "expected_price", "JPY"),
        "仮条件": ("pricing", "provisional_range", None),
        "仮条件価格": ("pricing", "provisional_range", None),
        "公募価格": ("pricing", "offer_price", "JPY"), "初値": ("pricing", "initial_price", "JPY"),
        "公募株数": ("offering", "new_shares", "shares"),
        "公募株式数": ("offering", "offering_breakdown", None),
        "売出株数(OA含む)": ("offering", "secondary_shares_including_oa", "shares"),
        "O.A.分": ("offering", "oa_shares", "shares"),
        "発行済株数": ("offering", "issued_shares", "shares"),
        "当選株数合計": ("offering", "total_offered_shares", "shares"),
        "OR": ("offering", "offering_ratio", "%"),
        "IPOの資金用途": ("business", "use_of_proceeds", None),
    }
    dates = {"仮条件決定日": "range_announcement", "BB期間": "bookbuilding_period",
             "抽選申込期間": "bookbuilding_period", "公募価格決定": "price_announcement",
             "当選発表日": "lottery_announcement", "購入申込期間": "purchase_period",
             "上場予定日": "listing_date", "上場日": "listing_date"}
    heading = ""
    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "table"]):
        if el.name != "table":
            heading = text(el)
            continue
        rows = []
        for tr in el.find_all("tr"):
            if tr.find_parent("table") is el:
                rows.append([cell_data(c, url) for c in tr.find_all(["td", "th"], recursive=False)])
        table = {"section": heading, "rows": rows, "html": str(el)}
        previous = el.find_previous(["p", "div", "h2", "h3", "h4", "h5"])
        table["preceding_text"] = text(previous) if previous and previous in root.descendants else ""
        result["raw_tables"].append(table)
        # Key/value tables only: never interpret a matrix header as a scalar field.
        if rows and max(map(len, rows)) == 2:
            for row in rows:
                if len(row) != 2:
                    continue
                key = unicodedata.normalize("NFKC", row[0]["text"]).replace(" ", "")
                raw = row[1]["text"]
                if key in mappings:
                    group, field, unit = mappings[key]
                    result[group][field] = measurement(raw, unit) if unit else {"raw": raw}
                    if field == "provisional_range":
                        nums = re.findall(r"\d[\d,]*(?:\.\d+)?", unicodedata.normalize("NFKC", raw))
                        result[group][field].update({"low": measurement(nums[0])["value"] if nums else None,
                                                    "high": measurement(nums[1])["value"] if len(nums) > 1 else None,
                                                    "unit": "JPY"})
                    if field in ("name", "website") and row[1]["links"]:
                        result["company"]["website"] = row[1]["links"][0]["url"]
                if key in dates:
                    result["schedule"][dates[key]] = {"raw": raw}
                if re.search(r"PER|PBR|配当", key):
                    result["valuation"][key] = {"raw": raw}
                if key == "主幹事証券":
                    result["company"]["lead_underwriter"] = raw
                if "狙い目証券会社" in key:
                    result["subscription_brokers"] = row[1]["links"]
        if not rows:
            continue
        headers = [c["text"] for c in rows[0]]
        header = " ".join(headers)
        group = None
        if "証券会社名" in header:
            group = "underwriters"
        elif "株主名" in header or ("氏名" in header and "株数" in header):
            group = "shareholders"
        elif "総会決議" in header:
            group = "stock_options"
        elif re.search(r"決算期|EPS|BPS", header) or (
            "業績" in heading and any("売上" in c["text"] for r in rows for c in r)):
            group = "financials"
        if group:
            # Named cells plus exact original table preserve rowspan, combined values,
            # period units and unavailable states without guessing their meaning.
            records = []
            for row in rows[1:]:
                if headers and not headers[0] and len(row) == len(headers) - 1:
                    row = [{"text": "", "italic": False}, *row]
                record = {}
                for index, cell in enumerate(row):
                    key = headers[index] if index < len(headers) else f"column_{index}"
                    key = key or "role"
                    entry = dict(cell)
                    if group == "underwriters" and re.search(r"割当|抽選|当選", key):
                        unit = "%" if "%" in key or "率" in key else "shares" if "株" in key or key == "割当数" else "lots"
                        estimated = True if "予想" in key or "抽選配分" in key or (source == "ipo96ut" and cell["italic"]) else None
                        entry.update(measurement(cell["text"], unit, estimated))
                    record[key] = entry
                records.append(record)
            result[group].append({"section": heading, "headers": headers, "records": records,
                                  "context": table["preceding_text"],
                                  "raw_table_index": len(result["raw_tables"]) - 1})
    synopsis = root.select_one(".ipo_syno")
    if synopsis:
        result["business"]["description_raw"] = text(synopsis)
        for a in synopsis.find_all("a", href=True):
            result["company"]["website"] = urljoin(url, a["href"])
    seen = set()
    for a in root.find_all("a", href=True):
        label, href = text(a), urljoin(url, a["href"])
        if re.search(r"目論見書|有価証券届出書|経営指標詳細|ロックアップ情報詳細|株式公開情報", label) and href not in seen:
            seen.add(href)
            result["documents"].append({"title": label, "url": href, "local_path": None})
    result["warnings"].append("Dates, financial units and compound cells retain source text; no unverified normalization is applied.")
    return result
