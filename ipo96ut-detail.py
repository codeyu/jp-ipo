#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取 kabu.96ut.com IPO 文章正文内容（自动过滤广告/联盟推广链接）

用法:
    python ipo96ut-detail.py                 # 爬取 ipo96ut.json 中的全部详情
    python ipo96ut-detail.py 9334            # 保存 9334.md 和 9334.json

示例:
    python ipo96ut-detail.py 500A --download-prospectus
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from ipo_detail_json import extract_details

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# 已知的广告/联盟营销域名（图片、链接指向这些域名的一律清除）
AD_DOMAINS = [
    "trafficgate.net",
    "accesstrade.net",
    "felmat.net",
    "a8.net",
    "moshimo.com",
    "af.moshimo.com",
    "linksynergy.com",
    "valuecommerce.ne.jp",
    "google.com/ads",
    "googlesyndication.com",
    "doubleclick.net",
]

# 明显是广告/推广/导航/侧边栏容器的 class 或 id 名称（小写精确匹配）
AD_CLASS_KEYWORDS = [
    "ad", "ads", "advert", "banner", "sponsor", "promo",
    "widget", "sidebar", "footer", "header", "nav", "menu",
    "breadcrumb", "share", "sns", "pr-box", "pr_box",
]

# 段落级过滤：包含这些关键词的整段文字大概率是广告免责声明
AD_TEXT_PATTERNS = [
    r"本ページには広告[・･].{0,10}プロモーション.{0,10}含み",
    r"^\[PR\]",
    r"^PR[:：]",
    r"アフィリエイト",
]


def is_ad_domain(url: str) -> bool:
    if not url:
        return False
    return any(domain in url for domain in AD_DOMAINS)


def has_ad_class(tag: Tag) -> bool:
    # class 属性本身就是由 token 组成的列表。逐项精确比较，避免把
    # ``already`` 之类正常 class 中的 ``ad`` 误当成广告容器。
    class_tokens = {value.lower() for value in tag.get("class", [])}
    tag_id = (tag.get("id") or "").lower()
    keywords = set(AD_CLASS_KEYWORDS)
    return bool(class_tokens & keywords) or tag_id in keywords


def strip_ads(root: Tag) -> None:
    """在给定的正文容器内递归删除广告元素"""

    # 1. 删除脚本/样式/注释
    for tag in root.find_all(["script", "style", "iframe", "noscript"]):
        tag.decompose()
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    # 2. 删除指向广告联盟域名的链接/图片（连同其外层 <a> 或容器一起删）
    for img in root.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if is_ad_domain(src):
            parent_a = img.find_parent("a")
            (parent_a or img).decompose()
            continue

    for a in list(root.find_all("a")):
        if a.decomposed:
            continue
        href = a.get("href", "")
        if is_ad_domain(href):
            a.decompose()

    # 3. 删除带广告/侧边栏/导航类名的容器
    for tag in list(root.find_all(True)):
        if tag.decomposed:
            continue
        if has_ad_class(tag):
            tag.decompose()

    # 4. 删除广告免责声明等特定文案段落
    for tag in list(root.find_all(["p", "div", "span"])):
        if tag.decomposed:
            continue
        text = tag.get_text(strip=True)
        if not text:
            continue
        if any(re.search(pat, text) for pat in AD_TEXT_PATTERNS):
            tag.decompose()

    # 5. 清理空标签（清广告后留下的空壳）
    changed = True
    while changed:
        changed = False
        for tag in list(root.find_all(True)):
            if tag.decomposed:
                continue
            if tag.name in ("br", "hr", "img"):
                continue
            if not tag.get_text(strip=True) and not tag.find("img"):
                tag.decompose()
                changed = True


def find_article_root(soup: BeautifulSoup) -> Tag:
    """定位正文容器：优先 <article>，其次常见 WordPress 正文 class"""
    candidates = [
        soup.find("article"),
        soup.find("div", class_=re.compile(r"entry-content")),
        soup.find("div", class_=re.compile(r"post-content")),
        soup.find("div", class_=re.compile(r"^content$")),
        soup.find("main"),
    ]
    for c in candidates:
        if c is not None:
            return c
    return soup.body or soup


def find_prospectus_pdf_url(soup: BeautifulSoup, article_url: str) -> str | None:
    """返回正文中“目論見書”所指向的 PDF；未找到时返回 None。"""
    for link in soup.find_all("a", href=True):
        label = link.get_text("", strip=True)
        if "目論見書" not in label:
            continue
        pdf_url = urljoin(article_url, link["href"])
        if urlparse(pdf_url).path.lower().endswith(".pdf"):
            return pdf_url
    return None


def download_prospectus(article_url: str, destination: Path) -> Path | None:
    """下载文章关联的目論見書 PDF；页面没有 PDF 时不创建文件。"""
    page_response = requests.get(article_url, headers=HEADERS, timeout=20)
    page_response.raise_for_status()
    soup = BeautifulSoup(page_response.text, "lxml")
    pdf_url = find_prospectus_pdf_url(soup, article_url)
    if not pdf_url:
        return None

    pdf_response = requests.get(pdf_url, headers=HEADERS, timeout=60)
    pdf_response.raise_for_status()
    # 防止网站返回错误 HTML 却被误存成 .pdf。
    if not pdf_response.content.startswith(b"%PDF-"):
        raise ValueError(f"目論見書链接未返回 PDF: {pdf_url}")

    filename = Path(unquote(urlparse(pdf_url).path)).name or "prospectus.pdf"
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / filename
    output_path.write_bytes(pdf_response.content)
    return output_path


def html_to_markdown(node: Tag, depth: int = 0, base_url: str = "") -> str:
    """把清洗后的 HTML 节点粗略转成 Markdown 文本"""
    lines = []

    def markdown_link(label: str, href: str) -> str:
        """将安全的 HTML 链接保留为 Markdown 链接。"""
        url = urljoin(base_url, href)
        if not label or not href or url.lower().startswith(("javascript:", "data:")):
            return label
        return f"[{label}]({url})"

    def walk(el, indent=0):
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                lines.append(text)
            return
        if not isinstance(el, Tag):
            return

        name = el.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            text = el.get_text(strip=True)
            if text:
                lines.append("\n" + "#" * level + " " + text + "\n")
            return
        if name == "table":
            _table_to_markdown(el, lines)
            return
        if name == "a":
            label = el.get_text("", strip=True)
            if label:
                lines.append(markdown_link(label, el.get("href", "")))
            return
        if name in ("em", "i") or re.search(
            r"font-style\s*:\s*(?:italic|oblique)", el.get("style", ""), re.I
        ):
            text = el.get_text("", strip=True)
            if text:
                lines.append(f"*{text}*")
            return
        if name in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                t = li.get_text(" ", strip=True)
                if t:
                    lines.append("- " + t)
            lines.append("")
            return
        if name == "br":
            lines.append("")
            return
        if name in ("p", "div", "section"):
            for child in el.children:
                walk(child, indent)
            text = el.get_text(strip=True)
            # p/div 后补空行分段（div 已递归处理子节点，这里只补换行）
            if name == "p" and text:
                lines.append("")
            return
        # 其它标签直接递归
        for child in el.children:
            walk(child, indent)

    def _table_to_markdown(table, lines):
        # 只取属于当前 table 的行。find_all 默认递归，会把 td 内嵌 table
        # 的行也当作外层表格的行，进而造成列数膨胀和重复内容。
        rows = [
            tr for tr in table.find_all("tr")
            if tr.find_parent("table") is table
        ]
        if not rows:
            return

        def inline_text(el):
            """保留常用行内格式，并跳过任何嵌套 table。"""
            if isinstance(el, NavigableString):
                return str(el)
            if not isinstance(el, Tag) or el.name == "table":
                return ""
            text = "".join(inline_text(child) for child in el.children)
            if el.name == "a":
                return markdown_link(text.strip(), el.get("href", ""))
            if (
                el.name in ("em", "i")
                or re.search(
                    r"font-style\s*:\s*(?:italic|oblique)", el.get("style", ""), re.I
                )
            ) and text.strip():
                return f"*{text.strip()}*"
            return text

        def text_without_nested_tables(cell):
            """取得单元格的自身文字，不把嵌套表格内容并入外层单元格。"""
            # 不使用 get_text(" ")，因为它会在相邻的日文 inline 元素间
            # 人为插入空格（例如「掲載 しています」）。
            return re.sub(r"\s+", " ", inline_text(cell)).strip()

        table_lines = []
        nested_table_notes = []
        for i, tr in enumerate(rows):
            # 单元格也只能取当前 tr 的直接子节点，避免收集嵌套表格的 cells。
            cells = tr.find_all(["th", "td"], recursive=False)
            row_text = []
            for cell in cells:
                cell_text = text_without_nested_tables(cell)
                if cell.find("table"):
                    # 嵌套表格所在单元格的说明文字应紧随其后，而不是塞进
                    # 外层 Markdown 表格的单元格（那会让阅读顺序颠倒）。
                    row_text.append("")
                    if cell_text:
                        nested_table_notes.append(cell_text)
                else:
                    row_text.append(cell_text)
            table_lines.append("| " + " | ".join(row_text) + " |")
            if i == 0:
                table_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
        lines.append("")
        lines.extend(table_lines)
        lines.append("")

        # html_to_markdown は table に出会えた時点で子要素を walk しないため、
        # 嵌套表格也要显式地继续输出，才能同时保留外层与内层表格。
        for nested_table in table.find_all("table"):
            if nested_table.find_parent("table") is table:
                _table_to_markdown(nested_table, lines)
        lines.extend(nested_table_notes)
        if nested_table_notes:
            lines.append("")

    walk(node)

    # 合并多余空行
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrape(url: str, code=None, include_json=False):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else soup.title.get_text(strip=True) if soup.title else ""

    root = find_article_root(soup)
    strip_ads(root)

    body_md = html_to_markdown(root, base_url=url)

    result = f"# {title}\n\n来源: {url}\n\n{body_md}"
    if include_json:
        return result, extract_details(root, url, "ipo96ut", code, body_md)
    return result


def load_ipo_items(json_path: Path) -> list[dict]:
    """读取 ipo96ut.json，并返回含 code 与 detail_url 的 IPO 记录。"""
    with json_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("ipo96ut.json 中缺少 items 列表")
    return [
        item for item in items
        if isinstance(item, dict) and item.get("code") and item.get("detail_url")
    ]


def main():
    parser = argparse.ArgumentParser(description="爬取 96ut.com IPO 文章正文（去广告）")
    parser.add_argument(
        "code",
        nargs="?",
        help="股票代码；省略时遍历 ipo96ut.json 的全部 detail_url",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        default=Path(__file__).with_name("ipo96ut.json"),
        help="IPO 列表 JSON 路径（默认：脚本同目录的 ipo96ut.json）",
    )
    parser.add_argument(
        "--download-prospectus",
        action="store_true",
        help="如页面存在目論見書链接，则下载对应 PDF",
    )
    parser.add_argument(
        "--pdf-dir",
        default="prospectuses",
        help="目論見書 PDF 的保存目录（默认：prospectuses）",
    )
    args = parser.parse_args()

    try:
        items = load_ipo_items(args.json_file)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"读取 IPO 列表失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.code:
        target_code = args.code.casefold()
        items = [item for item in items if str(item["code"]).casefold() == target_code]
        if not items:
            print(f"未在 {args.json_file} 中找到股票代码: {args.code}", file=sys.stderr)
            sys.exit(1)

    failed = False
    for item in items:
        code = str(item["code"])
        detail_url = str(item["detail_url"])
        try:
            content, details = scrape(detail_url, code, include_json=True)
        except requests.exceptions.HTTPError as e:
            print(f"{code} 请求失败: {e}", file=sys.stderr)
            failed = True
            continue
        except requests.exceptions.RequestException as e:
            print(f"{code} 网络错误: {e}", file=sys.stderr)
            failed = True
            continue

        output_path = Path(f"{code}.md")
        output_path.write_text(content, encoding="utf-8")
        json_path = Path(f"{code}.json")
        json_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{code} 已保存到: {output_path}, {json_path}")

        if not args.download_prospectus:
            continue
        try:
            pdf_path = download_prospectus(detail_url, Path(args.pdf_dir))
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"{code} 目論見書下载失败: {e}", file=sys.stderr)
            failed = True
            continue
        if pdf_path:
            for document in details["documents"]:
                if "目論見書" in document["title"]:
                    document["local_path"] = str(pdf_path.resolve())
            json_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{code} 目論見書 PDF 已保存到: {pdf_path}")
        else:
            print(f"{code} 未找到目論見書 PDF 链接。")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
