#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取 ipokiso.com 的 IPO 详情页。

用法:
    python ipokiso-detail.py          # 遍历 ipokiso.json 的全部详情页
    python ipokiso-detail.py 627A     # 保存 627A-pokiso.md 和 627A-pokiso.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from ipo_detail_json import extract_details


BASE_URL = "https://www.ipokiso.com/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def markdown_link(label: str, href: str, page_url: str) -> str:
    """将安全的页面链接保留为 Markdown 链接，并补全相对 URL。"""
    url = urljoin(page_url, href)
    if not label or not href or url.lower().startswith(("javascript:", "data:")):
        return label
    return f"[{label}]({url})"


def find_article_root(soup: BeautifulSoup) -> Tag:
    """IPOkiso 的详情页正文位于 #main 下的 #colum2.Mainbox。"""
    root = soup.select_one("#main #colum2.Mainbox")
    if root is None:
        raise ValueError("未找到 IPOkiso 详情页正文容器")
    return root


def clean_article(root: Tag) -> None:
    """删除正文中的面包屑、广告、投票组件和相关推荐导航。"""
    selectors = [
        ".pagenavi",
        ".js-vote",
        "[id^='ad_']",
        ".company_feature",
        ".twitterBox",
        ".go",
        ".goBack",
        ".goNext",
        ".bottomToTopPosition",
        ".bottomToTop",
        "script",
        "style",
        "iframe",
        "noscript",
    ]
    for selector in selectors:
        for tag in root.select(selector):
            tag.decompose()
    for comment in root.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def html_to_markdown(root: Tag, page_url: str) -> str:
    """转换 IPOkiso 正文，保留标题、表格、链接与斜体。"""
    lines: list[str] = []

    def inline_text(el) -> str:
        if isinstance(el, NavigableString):
            return str(el)
        if not isinstance(el, Tag):
            return ""
        if el.name == "br":
            return " ";
        if el.name == "table":
            return ""
        text = "".join(inline_text(child) for child in el.children)
        if el.name == "a":
            return markdown_link(text.strip(), el.get("href", ""), page_url)
        if el.name in ("em", "i") or re.search(
            r"font-style\s*:\s*(?:italic|oblique)", el.get("style", ""), re.I
        ):
            return f"*{text.strip()}*" if text.strip() else ""
        return text

    def table_to_markdown(table: Tag) -> None:
        # 只选属于当前 table 的行，防止将嵌套 table 拍平成一张表。
        rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
        if not rows:
            return
        rendered_rows = []
        for tr in rows:
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            values = [re.sub(r"\s+", " ", inline_text(cell)).strip() for cell in cells]
            rendered_rows.append(values)
        if not rendered_rows:
            return
        width = max(len(row) for row in rendered_rows)
        leading_blank_column = bool(rendered_rows[0] and not rendered_rows[0][0])
        for row in rendered_rows:
            missing_cells = width - len(row)
            if missing_cells <= 0:
                continue
            # IPOkiso 的证券公司表将“主幹事/幹事”放在首列；普通幹事行
            # 没有空 td，因此需在左侧补出这个逻辑上的空单元格。
            if leading_blank_column:
                row[:0] = [""] * missing_cells
            else:
                row.extend([""] * missing_cells)
        lines.append("")
        for index, row in enumerate(rendered_rows):
            lines.append("| " + " | ".join(row) + " |")
            if index == 0:
                lines.append("| " + " | ".join(["---"] * width) + " |")
        lines.append("")

    def walk(el) -> None:
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                lines.append(text)
            return
        if not isinstance(el, Tag):
            return
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = re.sub(r"\s+", " ", inline_text(el)).strip()
            if text:
                lines.append("\n" + "#" * int(el.name[1]) + " " + text + "\n")
            return
        if el.name == "table":
            table_to_markdown(el)
            return
        if el.name == "a":
            text = inline_text(el).strip()
            if text:
                lines.append(text)
            return
        if el.name in ("em", "i") or re.search(
            r"font-style\s*:\s*(?:italic|oblique)", el.get("style", ""), re.I
        ):
            text = inline_text(el).strip()
            if text:
                lines.append(text)
            return
        if el.name == "br":
            lines.append("")
            return
        if el.name == "p":
            text = re.sub(r"\s+", " ", inline_text(el)).strip()
            if text:
                lines.extend([text, ""])
            return
        for child in el.children:
            walk(child)

    walk(root)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def scrape(detail_url: str, code=None, include_json=False):
    """抓取一篇详情页并生成 Markdown。"""
    page_url = urljoin(BASE_URL, detail_url)
    response = requests.get(page_url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    root = find_article_root(soup)
    clean_article(root)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = html_to_markdown(root, page_url)
    markdown = f"# {title}\n\n来源: {page_url}\n\n{body}"
    if include_json:
        return markdown, extract_details(root, page_url, "ipokiso", code, body)
    return markdown


def load_ipo_items(json_path: Path) -> list[dict]:
    with json_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("ipokiso.json 中缺少 items 列表")
    return [
        item for item in items
        if isinstance(item, dict) and item.get("code") and item.get("detail_url")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="爬取 IPOkiso IPO 详情页")
    parser.add_argument("code", nargs="?", help="股票代码；省略时遍历全部记录")
    parser.add_argument(
        "--json-file",
        type=Path,
        default=Path(__file__).with_name("ipokiso.json"),
        help="IPO 列表 JSON 路径（默认：脚本同目录的 ipokiso.json）",
    )
    args = parser.parse_args()

    try:
        items = load_ipo_items(args.json_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"读取 IPO 列表失败: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.code:
        items = [item for item in items if str(item["code"]).casefold() == args.code.casefold()]
        if not items:
            print(f"未在 {args.json_file} 中找到股票代码: {args.code}", file=sys.stderr)
            sys.exit(1)

    failed = False
    for item in items:
        code = str(item["code"])
        try:
            content, details = scrape(str(item["detail_url"]), code, include_json=True)
        except (requests.exceptions.RequestException, ValueError) as exc:
            print(f"{code} 爬取失败: {exc}", file=sys.stderr)
            failed = True
            continue
        output_path = Path(f"{code}-pokiso.md")
        output_path.write_text(content, encoding="utf-8")
        Path(f"{code}-pokiso.json").write_text(
            json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{code} 已保存到: {output_path}, {code}-pokiso.json")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
