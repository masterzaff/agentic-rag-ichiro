import utils.config as config
from utils.functions import log
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString


def load_title_map_from_index(index_path: Path) -> dict[str, str]:
    """Parse index.html for page titles."""
    title_map = {}
    if not index_path.exists():
        return title_map

    try:
        soup = BeautifulSoup(
            index_path.read_text(encoding="utf-8", errors="ignore"), "lxml"
        )
        for a in soup.find_all("a", href=True):
            if m := config.INTERNAL_LINK_RE.match(a["href"]):
                fname = Path(m.group(1)).name
                title_map.setdefault(fname, a.get_text(" ", strip=True) or fname)
    except Exception as e:
        log(f"Warning: Failed to load title map: {e}", echo=False)

    return title_map


def select_main_content(soup: BeautifulSoup) -> Tag:
    """Select main content area."""
    if mc := soup.select_one("#main-content"):
        return mc

    candidates = [
        (len(el.get_text(" ", strip=True)), el)
        for el in soup.find_all(["main", "article", "section", "div"])
        if len(el.get_text(" ", strip=True)) > 300
    ]

    return candidates[0][1] if candidates else (soup.body or soup)


def strip_noise(soup: BeautifulSoup):
    """Remove scripts, styles, and breadcrumbs."""
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    if bc := soup.select_one("#breadcrumbs"):
        bc.decompose()


def rewrite_internal_link(a: Tag, title_map: dict) -> str | None:
    """Turn <a href="something_123.html#..."> into your chosen representation."""
    text = a.get_text(" ", strip=True)
    href = a.get("href", "")
    m = config.INTERNAL_LINK_RE.match(href)
    if not m:
        if href.startswith(("http://", "https://")):
            return f"{text} ({href})" if text else href
        return text

    fname = Path(m.group(1)).name
    title = title_map.get(fname, fname)

    if config.LINK_MODE == "wiki":
        return f"[[{title}]]"
    if config.LINK_MODE == "title":
        return title
    if config.LINK_MODE == "url":
        return f"{title} ({fname})"
    if config.LINK_MODE == "strip":
        return text
    return text


def to_text(root: Tag, title_map: dict) -> str:
    lines = []

    def walk(node):
        if isinstance(node, NavigableString):
            s = str(node)
            if s.strip():
                lines.append(s.strip())
            return
        if not isinstance(node, Tag):
            return

        name = node.name.lower()

        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            title = node.get_text(" ", strip=True)
            underline = "=" if level <= 2 else "-"
            lines.append(title)
            lines.append(underline * len(title))
            lines.append("")
            return

        if name == "p":
            t = node.get_text(" ", strip=True)
            if t:
                lines.append(t)
                lines.append("")
            return

        if name == "pre":
            code = node.get_text("\n", strip=True)
            lines.append("```")
            lines.append(code)
            lines.append("```")
            lines.append("")
            return
        if name == "code":
            lines.append(f"`{node.get_text(strip=True)}`")
            return

        if name in {"ul", "ol"}:
            bullet = "-" if name == "ul" else "1."
            for li in node.find_all("li", recursive=False):
                item = li.get_text(" ", strip=True)
                if item:
                    lines.append(f"{bullet} {item}")
                for child in li.find_all(["ul", "ol"], recursive=False):
                    walk(child)
            lines.append("")
            return

        if name == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                lines.append(" | ".join(["---"] * len(rows[0].split(" | "))))
                lines.extend(rows)
                lines.append("")
            return

        if name == "a":
            repl = rewrite_internal_link(node, title_map)
            if repl:
                lines.append(repl)
            return

        if name == "br":
            lines.append("")
            return

        for child in node.children:
            walk(child)

    walk(root)

    out = []
    prev_blank = False
    for ln in lines:
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        out.append(ln.rstrip())
        prev_blank = is_blank
    return "\n".join(out).strip()


def clean_file(path: Path, title_map: dict) -> str:
    """Clean a single HTML file and return text content."""
    try:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
        strip_noise(soup)
        main = select_main_content(soup)

        page_title = (soup.title.string or "").strip() if soup.title else ""
        if not page_title:
            page_title = title_map.get(path.name, path.stem)

        body = to_text(main, title_map)
        if page_title and page_title not in body[:200]:
            body = f"{page_title}\n{'='*len(page_title)}\n\n{body}"

        body = re.sub(r"[ \t]+\n", "\n", body)
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body
    except Exception as e:
        log(f"Warning: Failed to clean {path.name}: {e}", echo=False)
        return ""


def clean_html_files():
    """Clean HTML files and save as text."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in config.HTML_DIR.rglob("*.html") if p.name.lower() != "index.html"
    ]
    if not files:
        log("No HTML files found", echo=True)
        return 0

    title_map = load_title_map_from_index(config.INDEX_FILE)
    log(f"Cleaning {len(files)} HTML files...", echo=True)

    count = 0
    for f in files:
        try:
            if cleaned := clean_file(f, title_map):
                (config.DATA_DIR / f"{f.stem}.txt").write_text(
                    cleaned, encoding="utf-8"
                )
                count += 1
        except Exception as e:
            log(f"Warning: Failed to save {f.name}: {e}", echo=False)

    if count == 0:
        log("No files cleaned", echo=True)
        return 0

    log(f"Cleaned {count} files", echo=True)
    return count
