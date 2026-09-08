#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_96ut_ipo.py

抓取 96ut.com IPO「予想」表格数据：
    https://96ut.com/ipo/yoso.php?year=<YEAR>

<YEAR> 可以是 2010 ~ 2026 中的任意一年，或者字符串 "now"（当前年度）。
不传 --year 参数时，默认遍历 2010 到 2026 以及 "now"。

用法示例：
    # 只抓一年
    python3 scrape_96ut_ipo.py --year 2026

    # 抓 "now"（当前进行中的年度）
    python3 scrape_96ut_ipo.py --year now

    # 遍历 2010~2026 + now（默认行为，不加 --year 即可）
    python3 scrape_96ut_ipo.py

    # 自定义范围
    python3 scrape_96ut_ipo.py --start 2015 --end 2020

    # 指定输出目录 & 只导出 CSV（默认 CSV + JSON 都导出）
    python3 scrape_96ut_ipo.py --year 2026 --outdir ./out --format csv

依赖：
    pip install requests beautifulsoup4 lxml
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://96ut.com/ipo/yoso.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,zh-CN;q=0.9,en;q=0.8",
    "Referer": "https://96ut.com/ipo/yoso.php",
}

# 表格列的语义名称（按 96ut.com 页面里 <th> 的顺序）
FIELD_NAMES = [
    "name",         # 銘柄名
    "underwriter",  # 主幹事
    "listing_date", # 上場日
    "market",       # 市場
    "code",         # 証券コード
    "price_range",  # 仮条件（想定レンジ）
    "price_final",  # 仮条件 想定⇒公開（公開価格）
    "price_before1",# BB前（当初予想）
    "price_before2",# BB前（直前予想）
    "grade",        # 黒澤評価グレード
    "grade_votes",  # 黒澤評価 投票数
    "reader_forecast",     # 読者予想 初値平均
    "reader_forecast_n",   # 読者予想 件数
    "stance_bars",  # スタンス予想グラフ（s/a/b/c/d 比率）
    "hatsune_bars", # 初値予想グラフ（s/a/b/c/d 比率）
    "hatsune",      # 初値（実際の初値）
    "vote_status",  # 投票欄のステータス（募集中 / 締切 など）
    "detail_url",   # 個別ページURL
]


def fetch_html(year: Any, session: requests.Session, timeout: int = 20, retries: int = 3) -> Optional[str]:
    """请求指定 year 的页面，返回 HTML 文本。失败返回 None。"""
    params = {}
    if year is not None:
        params["year"] = year

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            # 该站点常见编码为 shift_jis / utf-8，requests 的自动探测有时不准，做个兜底
            if not resp.encoding or resp.encoding.lower() in ("iso-8859-1",):
                resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.RequestException as e:
            last_err = e
            wait = 1.5 * attempt
            print(f"  [warn] year={year} 第{attempt}次请求失败: {e}，{wait:.1f}s 后重试...", file=sys.stderr)
            time.sleep(wait)
    print(f"  [error] year={year} 请求最终失败: {last_err}", file=sys.stderr)
    return None


def _text(el) -> str:
    """安全提取节点文本，去除多余空白。"""
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _bar_percentages(cell, css_prefix: str) -> List[float]:
    """
    从一组 <div class="bar_xxx_s/a/b/c/d" style="max-width: NN.N%"> 中提取百分比列表。
    css_prefix 例如 "bar_stance" 或 "bar_hatune"。
    返回顺序固定为 [s, a, b, c, d]。
    """
    result = []
    for suffix in ("s", "a", "b", "c", "d"):
        div = cell.find("div", class_=f"{css_prefix}_{suffix}")
        pct = 0.0
        if div is not None:
            style = div.get("style", "")
            m = re.search(r"max-width:\s*([\d.]+)%", style)
            if m:
                pct = float(m.group(1))
        result.append(pct)
    return result


def parse_row(tds: List, base_url: str) -> Optional[Dict[str, Any]]:
    """解析一行 <tr> 中的 <td> 列表，返回字段字典。列数不足 9 则视为无效行返回 None。"""
    if len(tds) < 9:
        return None

    row: Dict[str, Any] = {}

    # --- 第1列：銘柄名 (主幹事) ---
    td0 = tds[0]
    links = td0.find_all("a")
    if links:
        row["name"] = _text(links[0])
        detail_href = links[0].get("href", "")
        row["detail_url"] = requests.compat.urljoin(base_url, detail_href) if detail_href else ""
        underwriters = [_text(a) for a in links[1:]]
        row["underwriter"] = "/".join([u for u in underwriters if u])
    else:
        row["name"] = _text(td0)
        row["detail_url"] = ""
        row["underwriter"] = ""

    # --- 第2列：上場日 ---
    row["listing_date"] = _text(tds[1]).replace(" ", "")

    # --- 第3列：市場 [code] ---
    td2 = tds[2]
    code_link = td2.find("a")
    row["code"] = _text(code_link) if code_link else ""
    market_text = _text(td2)
    # 去掉 code 部分，剩下的当作市场简称，如 "東M"、"JQS"
    market_only = market_text.replace(row["code"], "").replace("[", "").replace("]", "").strip()
    row["market"] = market_only

    # --- 第4列：仮条件 想定⇒公開 ---
    td3 = tds[3]
    spans = td3.find_all("span")
    row["price_range"] = _text(spans[0]) if spans else ""
    # 完整文本形如 "3,460⇒3,460" 或 "570⇒500"，取箭头后面的最终值
    full_text = _text(td3)
    m = re.search(r"⇒\s*([\d,]+|未)", full_text)
    row["price_final"] = m.group(1) if m else ""

    # --- 第5列：BB前 / 直前 ---
    td4 = tds[4]
    bb_text = _text(td4)
    bb_parts = bb_text.split()
    row["price_before1"] = bb_parts[0] if len(bb_parts) > 0 else ""
    row["price_before2"] = bb_parts[1] if len(bb_parts) > 1 else ""

    # --- 第6列：黒澤評価 / 読者予想 ---
    td5 = tds[5]
    strong = td5.find("strong")
    if strong:
        gtext = _text(strong)  # 形如 "B (6)"
        gm = re.match(r"([A-Za-z]+)\s*\(?(\d+)?\)?", gtext)
        row["grade"] = gm.group(1) if gm else gtext
        row["grade_votes"] = gm.group(2) if gm and gm.group(2) else ""
    else:
        row["grade"] = ""
        row["grade_votes"] = ""
    reader_link = td5.find("a")
    if reader_link:
        rtext = _text(reader_link)  # 形如 "3,492 (5件)"
        rm = re.match(r"([\d,]+)\s*\((\d+)件\)", rtext)
        if rm:
            row["reader_forecast"] = rm.group(1)
            row["reader_forecast_n"] = rm.group(2)
        else:
            row["reader_forecast"] = rtext
            row["reader_forecast_n"] = ""
    else:
        row["reader_forecast"] = ""
        row["reader_forecast_n"] = ""

    # --- 第7列：スタンス予想グラフ ---
    td6 = tds[6]
    row["stance_bars"] = _bar_percentages(td6, "bar_stance")
    row["hatsune_bars"] = _bar_percentages(td6, "bar_hatune")

    # --- 第8列：初値 ---
    row["hatsune"] = _text(tds[7])

    # --- 第9列：投票 ---
    row["vote_status"] = _text(tds[8])

    return row


def parse_table(html: str, base_url: str) -> List[Dict[str, Any]]:
    """解析整页 HTML，返回所有有效行的数据列表。"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="kuro")
    if table is None:
        # 兜底：找页面里最大的一个 table
        tables = soup.find_all("table")
        table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)
    if table is None:
        return []

    rows_out = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue  # 跳过表头 <th> 行和空的分隔行 <tr class="odd"></tr>
        parsed = parse_row(tds, base_url)
        if parsed:
            rows_out.append(parsed)
    return rows_out


def scrape_year(year: Any, session: requests.Session, sleep_sec: float = 1.5) -> List[Dict[str, Any]]:
    label = "now" if year == "now" else str(year)
    print(f"[*] 抓取 year={label} ...")
    html = fetch_html(year, session)
    if not html:
        return []
    rows = parse_table(html, BASE_URL)
    for r in rows:
        r["year"] = label
    print(f"    -> 解析到 {len(rows)} 条记录")
    time.sleep(sleep_sec)
    return rows


def save_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        print(f"[!] 无数据，跳过 CSV 输出: {path}")
        return
    fieldnames = ["year"] + FIELD_NAMES
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            row_copy = dict(r)
            # 列表字段转成字符串，方便 CSV 查看
            row_copy["stance_bars"] = ",".join(f"{v:g}" for v in r.get("stance_bars", []))
            row_copy["hatsune_bars"] = ",".join(f"{v:g}" for v in r.get("hatsune_bars", []))
            writer.writerow(row_copy)
    print(f"[+] CSV 已保存: {path} ({len(rows)} 行)")


def save_json(rows: List[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"[+] JSON 已保存: {path} ({len(rows)} 行)")


def build_year_list(args: argparse.Namespace) -> List[Any]:
    if args.year is not None:
        # 单个 year 参数：数字或 "now"
        if args.year.lower() == "now":
            return ["now"]
        return [int(args.year)]

    # 未指定 --year：遍历 start..end，并追加 "now"
    years: List[Any] = list(range(args.start, args.end + 1))
    if args.include_now:
        years.append("now")
    return years


def main():
    parser = argparse.ArgumentParser(description="抓取 96ut.com IPO 予想 表格数据")
    parser.add_argument("--year", type=str, default=None,
                         help="指定单一年份 (2010-2026) 或 'now'。不指定则遍历 --start 到 --end (+ now)。")
    parser.add_argument("--start", type=int, default=2010, help="遍历起始年份，默认 2010")
    parser.add_argument("--end", type=int, default=2026, help="遍历结束年份，默认 2026")
    parser.add_argument("--include-now", action="store_true", default=True,
                         help="遍历模式下是否额外抓取 year=now，默认开启")
    parser.add_argument("--no-include-now", dest="include_now", action="store_false",
                         help="遍历模式下不抓取 year=now")
    parser.add_argument("--outdir", type=str, default="./output", help="输出目录，默认 ./output")
    parser.add_argument("--format", type=str, choices=["csv", "json", "both"], default="both",
                         help="输出格式，默认 both（csv + json）")
    parser.add_argument("--sleep", type=float, default=1.5, help="每次请求之间的间隔秒数，默认 1.5s")
    parser.add_argument("--per-year-files", action="store_true",
                         help="除了合并文件外，额外为每个年份单独输出一份文件")
    args = parser.parse_args()

    years = build_year_list(args)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    all_rows: List[Dict[str, Any]] = []

    for y in years:
        rows = scrape_year(y, session, sleep_sec=args.sleep)
        all_rows.extend(rows)
        if args.per_year_files and rows:
            label = "now" if y == "now" else str(y)
            if args.format in ("csv", "both"):
                save_csv(rows, outdir / f"ipo_yoso_{label}.csv")
            if args.format in ("json", "both"):
                save_json(rows, outdir / f"ipo_yoso_{label}.json")

    print(f"\n[=] 全部完成，总计 {len(all_rows)} 条记录")

    if args.format in ("csv", "both"):
        save_csv(all_rows, outdir / "ipo_yoso_all.csv")
    if args.format in ("json", "both"):
        save_json(all_rows, outdir / "ipo_yoso_all.json")


if __name__ == "__main__":
    main()
