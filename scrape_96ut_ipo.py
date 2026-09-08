#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取 kabu.96ut.com IPO 文章正文内容（自动过滤广告/联盟推广链接）

用法:
    python scrape_96ut_ipo.py <文章URL> [-o 输出文件.md]

示例:
    python scrape_96ut_ipo.py https://kabu.96ut.com/article/ipo/2026034/
    python scrape_96ut_ipo.py https://kabu.96ut.com/article/ipo/2026001/ -o to_books.md
"""

import argparse
import re
import sys

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

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

# 明显是广告/推广/导航/侧边栏容器的 class 或 id 关键字（小写包含匹配）
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
    attrs = " ".join(tag.get("class", []) + [tag.get("id", "") or ""]).lower()
    if not attrs:
        return False
    # 避免误伤真正的正文容器 (例如 class 里含 "entry-content" 不应被 "content" 关键词误杀,
    # 这里只匹配广告类关键词，不含 "content")
    return any(kw in attrs for kw in AD_CLASS_KEYWORDS)


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


def html_to_markdown(node: Tag, depth: int = 0) -> str:
    """把清洗后的 HTML 节点粗略转成 Markdown 文本"""
    lines = []

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
        rows = table.find_all("tr")
        if not rows:
            return
        table_lines = []
        for i, tr in enumerate(rows):
            cells = tr.find_all(["th", "td"])
            row_text = [c.get_text(" ", strip=True) for c in cells]
            table_lines.append("| " + " | ".join(row_text) + " |")
            if i == 0:
                table_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
        lines.append("")
        lines.extend(table_lines)
        lines.append("")

    walk(node)

    # 合并多余空行
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrape(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else soup.title.get_text(strip=True) if soup.title else ""

    root = find_article_root(soup)
    strip_ads(root)

    body_md = html_to_markdown(root)

    result = f"# {title}\n\n来源: {url}\n\n{body_md}"
    return result


def main():
    parser = argparse.ArgumentParser(description="爬取 96ut.com IPO 文章正文（去广告）")
    parser.add_argument(
        "url",
        nargs="?",
        default="https://kabu.96ut.com/article/ipo/2026034/",
        help="文章 URL",
    )
    parser.add_argument("-o", "--output", help="输出 Markdown 文件路径")
    args = parser.parse_args()

    try:
        content = scrape(args.url)
    except requests.exceptions.HTTPError as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"网络错误: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"已保存到: {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
