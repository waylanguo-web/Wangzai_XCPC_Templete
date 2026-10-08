import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name
    PYGMENTS_OK = True
except ImportError:
    PYGMENTS_OK = False


def check_dependencies():
    """Check if optional dependencies are available."""
    missing = []
    if fitz is None:
        missing.append("pymupdf (PDF export will be disabled)")
    if not PYGMENTS_OK:
        missing.append("pygments (code highlighting will use built-in highlighter)")
    return missing


ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "正文"
DEFAULT_OUTPUT_DIR = ROOT / "dist" / "book"
PROJECT_TITLE = "Wangzai_XCPC_Templete"

# Optional cover configuration. The builder works without these files.
COVER_IMAGE_CANDIDATES = [
    ROOT / "cover.png",
    ROOT / "cover.jpg",
    ROOT / "assets" / "cover.png",
    ROOT / "assets" / "cover.jpg",
]
COVER_VERSION = ""
COVER_AUTHOR = ""


@dataclass
class Heading:
    level: int
    text: str
    anchor: str
    display_text: str = ""
    marker: str = ""
    logical_level: int = 0


@dataclass
class Chapter:
    path: Path
    title: str
    title_raw: str
    content: str
    headings: list[Heading] = field(default_factory=list)


# ------------------------------
# CLI / discovery
# ------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a book-style Markdown/HTML/PDF matching the WIDA/XCPC reference layout."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--title", default=PROJECT_TITLE)
    parser.add_argument("--toc-depth", type=int, default=5,
                        help="TOC heading depth: 1=chapter children, 2=grandchildren, etc.")
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--browser", default="")
    parser.add_argument("--cover-image", default="",
                        help="optional cover image path")
    parser.add_argument("--version", default=COVER_VERSION)
    parser.add_argument("--author", default=COVER_AUTHOR)
    parser.add_argument(
        "--pdf-timeout", type=int, default=600,
        help="maximum seconds for one browser PDF export; 0 disables timeout"
    )
    return parser.parse_args()


def is_front_matter(chapter):
    return chapter.title.strip() in {"使用说明", "使用指南", "模板说明"}


def chapter_group_key(path):
    stem = path.stem.strip()
    m = re.match(r"^(\d+)\s*[-_]?\s*([ABab])(?:$|[-_\s])", stem)
    if m:
        return (0, int(m.group(1)), m.group(2).upper())
    m = re.match(r"^(\d+)", stem)
    if m:
        return (0, int(m.group(1)), "")
    return (1, stem.lower())


def chapter_merge_key(path):
    stem = path.stem.strip()
    m = re.match(r"^(\d+)\s*[-_]?\s*[ABab](?:$|[-_\s])", stem)
    return (int(m.group(1)),) if m else None


def strip_leading_h1(content):
    lines = content.splitlines()
    out = []
    removed = False
    for line in lines:
        if not removed and re.match(r"^#\s+.*\S\s*$", line):
            removed = True
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def discover_chapters():
    files = sorted(BOOK_DIR.glob("*.md"), key=chapter_group_key)
    if not files:
        raise RuntimeError(f"cannot find markdown chapters under: {BOOK_DIR}")

    grouped = []
    used = set()
    for i, path in enumerate(files):
        if path in used:
            continue
        merge_key = chapter_merge_key(path)
        members = [path]
        if merge_key is not None:
            for other in files[i + 1:]:
                if other in used:
                    continue
                if chapter_merge_key(other) == merge_key:
                    members.append(other)
        for member in members:
            used.add(member)

        parts = []
        title_raw = path.stem
        for member in members:
            content = member.read_text(encoding="utf-8").replace("\ufeff", "").strip() + "\n"
            if not parts:
                for line in content.splitlines():
                    m = re.match(r"^#\s+(.*\S)\s*$", line)
                    if m:
                        title_raw = m.group(1).strip()
                        break
            parts.append(strip_leading_h1(content))

        combined = "\n\n".join(x.strip() for x in parts if x.strip()) + "\n"
        title = clean_chapter_title(title_raw)
        grouped.append(Chapter(path=members[0], title=title, title_raw=title_raw, content=combined))

    return grouped

def clean_chapter_title(text: str) -> str:
    s = text.strip()
    s = re.sub(r"^第\s*[0-9０-９一二三四五六七八九十百千万零〇两]+\s*章\s*[：:、.．\-]?\s*", "", s)
    s = re.sub(r"^[0-9０-９]+\s*[ABab]?\s*[.、:：\-]?\s*", "", s)
    s = re.sub(r"^[0-9０-９]+[ABab](?:$|[-_\s])\s*", "", s, flags=re.I)
    return s.strip()

def chapter_header_title(chapter: Chapter, index: int = 1) -> str:
    return f"第{chapter_number_for(chapter, index)}章：{chapter.title}"

def chapter_display_title(chapter: Chapter, index: int) -> str:
    return f"{index} {chapter.title}"


def chapter_body_title(chapter: Chapter, index: int) -> str:
    for line in chapter.content.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line.strip())
        if m and is_duplicate_chapter_heading(chapter, m.group(2).strip()):
            return m.group(2).strip()
    return chapter_header_title(chapter, index)

def make_anchor(text, used):
    base = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", text, flags=re.UNICODE).strip().lower()
    base = re.sub(r"\s+", "-", base)
    if not base:
        base = "section"
    count = used.get(base, 0)
    used[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def chapter_number_for(chapter, fallback=1):
    """Return the logical chapter number from the merged source filename/title."""
    stem = chapter.path.stem.strip()
    m = re.match(r"^(\d+)", stem)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:第\s*)?(\d+)\s*章", chapter.title_raw or "")
    if m:
        return int(m.group(1))
    for hline in chapter.content.splitlines():
        m = re.match(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\s+", hline.strip())
        if m:
            return int(m.group(2).split('.')[0])
    return fallback


def split_existing_heading_number(text):
    m = re.match(r"^(\d+(?:\.\d+)*)\s+(.*\S)\s*$", text.strip())
    if not m:
        return None, text.strip()
    return m.group(1), m.group(2).strip()


def unescape_markdown_text(text: str) -> str:
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", text)


def assign_heading_numbers(chapter, headings, fallback_number=1):
    """Preserve explicit heading numbers; generate missing 4.1/4.1.1 style numbers."""
    chapter_no = chapter_number_for(chapter, fallback_number)
    counters = [0] * 7
    if not headings:
        return

    base_level = min(h.level for h in headings)

    for h in headings:
        h.marker = f"WZHEAD-{h.anchor}"
        h.logical_level = max(2, h.level - base_level + 2)
        explicit, title = split_existing_heading_number(h.text)
        if explicit:
            nums = [int(x) for x in explicit.split('.')]
            h.logical_level = max(2, len(nums))
            # Explicit numbering is source-of-truth, but synchronize counters so
            # following unnumbered headings continue from it.
            if nums and nums[0] == chapter_no:
                for level, value in enumerate(nums[1:], start=2):
                    if level <= 6:
                        counters[level] = value
                        for deeper in range(level + 1, 7):
                            counters[deeper] = 0
            h.display_text = f"{explicit} {title}"
            continue

        level = h.logical_level
        if level < 2:
            h.display_text = h.text
            continue
        if level == 2:
            counters[2] += 1
            for deeper in range(3, 7):
                counters[deeper] = 0
        else:
            # If the source jumps a heading level, inherit the nearest existing parent.
            if counters[2] == 0:
                counters[2] = 1
            for parent in range(3, level):
                if counters[parent] == 0:
                    counters[parent] = 1
            counters[level] += 1
            for deeper in range(level + 1, 7):
                counters[deeper] = 0

        parts = [str(chapter_no)] + [str(counters[x]) for x in range(2, level + 1)]
        h.display_text = f"{'.'.join(parts)} {h.text}"


def collect_headings(chapters):
    used = {}
    numbered_index = 0
    for chapter in chapters:
        chapter.headings.clear()
        for line in chapter.content.splitlines():
            m = re.match(r"^(#{2,6})\s+(.*\S)\s*$", line)
            if not m:
                continue
            text_value = m.group(2).strip()
            if is_duplicate_chapter_heading(chapter, text_value):
                continue
            chapter.headings.append(
                Heading(level=len(m.group(1)), text=text_value,
                        anchor=make_anchor(text_value, used))
            )
        if not is_front_matter(chapter):
            numbered_index += 1
            assign_heading_numbers(chapter, chapter.headings, numbered_index)
        else:
            for h in chapter.headings:
                h.marker = f"WZHEAD-{h.anchor}"
                h.display_text = h.text


# ------------------------------
# Progress helpers
# ------------------------------

def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def show_progress(label, current, total, started_at):
    total = max(1, total)
    current = min(max(0, current), total)
    ratio = current / total
    width = 28
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    elapsed = format_elapsed(time.monotonic() - started_at)
    print(
        f"\r[book-builder] {label} [{bar}] {current}/{total} {ratio:>6.1%} elapsed {elapsed}",
        end="", flush=True,
    )


# ------------------------------
# Inline Markdown
# ------------------------------

def render_inline(text):
    result = []
    pos = 0
    token_re = re.compile(
        r"(`+.*?`+|\$(?:\\.|[^$\n])+\$|\\\((?:\\.|[^)])+\\\)|\\[\\`*_{}\[\]()#+\-.!|]|"
        r"!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|"
        r"\*\*(.+?)\*\*|__(.+?)__|~~(.+?)~~|"
        r"(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)|"
        r"</?[A-Za-z][^>]*>)",
        re.DOTALL,
    )
    for match in token_re.finditer(text):
        result.append(html.escape(unescape_markdown_text(text[pos:match.start()])))
        token = match.group(0)

        if token.startswith("`"):
            ticks = len(token) - len(token.lstrip("`"))
            if len(token) >= ticks * 2 and token.endswith("`" * ticks):
                code = token[ticks:-ticks].strip()
                result.append(f'<code class="inline-code">{html.escape(code)}</code>')
            else:
                result.append(html.escape(token))
        elif token.startswith("\\") and len(token) == 2:
            result.append(html.escape(token[1]))
        elif token.startswith("$") or token.startswith(r"\("):
            result.append(token)
        elif match.group(2) is not None:
            alt, src = match.group(2), match.group(3)
            result.append(
                f'<img class="inline-image" src="{html.escape(src, quote=True)}" '
                f'alt="{html.escape(alt, quote=True)}">'
            )
        elif match.group(4) is not None:
            label, url = match.group(4), match.group(5)
            result.append(f'<a href="{html.escape(url, quote=True)}">{render_inline(label)}</a>')
        elif match.group(6) is not None or match.group(7) is not None:
            result.append(f"<strong>{render_inline(match.group(6) or match.group(7))}</strong>")
        elif match.group(8) is not None:
            result.append(f"<del>{render_inline(match.group(8))}</del>")
        elif match.group(9) is not None or match.group(10) is not None:
            result.append(f"<em>{render_inline(match.group(9) or match.group(10))}</em>")
        else:
            # Allow lightweight HTML used by the book, e.g. <mark>, <span>, <br>.
            result.append(token)
        pos = match.end()
    result.append(html.escape(unescape_markdown_text(text[pos:])))
    return "".join(result)


# ------------------------------
# Code highlighting
# ------------------------------

LANG_ALIASES = {
    "c++": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp", "h": "cpp",
    "py": "python", "js": "javascript", "ts": "typescript",
    "sh": "bash", "shell": "bash", "zsh": "bash",
    "txt": "text", "plain": "text",
}

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
    "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
    "class", "compl", "concept", "const", "consteval", "constexpr", "constinit",
    "const_cast", "continue", "co_await", "co_return", "co_yield", "decltype",
    "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit",
    "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline",
    "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq",
    "nullptr", "operator", "or", "or_eq", "private", "protected", "public", "reflexpr",
    "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof",
    "static", "static_assert", "static_cast", "struct", "switch", "template", "this",
    "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union",
    "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
}
CPP_TYPES = {
    "size_t", "ptrdiff_t", "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t",
    "uint32_t", "uint64_t", "string", "vector", "array", "map", "set", "multiset", "multimap",
    "unordered_map", "unordered_set", "pair", "tuple", "deque", "queue", "stack", "priority_queue",
    "bitset", "function", "optional", "variant", "any", "i64", "u64", "ll", "ld", "LL",
}
CPP_BUILTINS = {
    "cin", "cout", "cerr", "clog", "endl", "gcd", "max", "min", "abs", "swap", "sort", "reverse",
    "lower_bound", "upper_bound", "find", "begin", "end", "sqrt", "pow", "sin", "cos", "log2",
}
PY_KEYWORDS = {
    "and", "as", "assert", "async", "await", "break", "case", "class", "continue", "def", "del",
    "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in",
    "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try",
    "while", "with", "yield",
}


# Compile once. The previous built-in highlighter compiled this regex for every
# source line, which becomes extremely slow on a large template book.
SIMPLE_TOKEN_RE = re.compile(
    r"(//.*$|/\*.*?\*/|\#.*$|//|\b\d+(?:\.\d+)?(?:e[+-]?\d+)?[uUlLfF]*\b|"
    r"""\b[A-Za-z_]\w*\b|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|==|!=|<=|>=|->|\+\+|--|&&|\|\||<<|>>|::|[+\-*/%=<>!&|^~?:.,;(){}\[\]])""",
    re.IGNORECASE,
)


def lexer_for(language):
    language = LANG_ALIASES.get((language or "").strip().lower(), (language or "").strip().lower())
    if not PYGMENTS_OK:
        return None
    if not language:
        return TextLexer()
    try:
        return get_lexer_by_name(language)
    except Exception:
        return TextLexer()


def simple_highlight_line(line, language):
    language = LANG_ALIASES.get((language or "").strip().lower(), (language or "").strip().lower())
    if language not in {"cpp", "c", "java", "javascript", "typescript", "python", "bash"}:
        return html.escape(line)

    # Tokenizer deliberately handles comments/strings before identifiers to avoid
    # highlighting words inside literals/comments.
    out = []
    pos = 0
    for m in SIMPLE_TOKEN_RE.finditer(line):
        out.append(html.escape(line[pos:m.start()]))
        tok = m.group(0)
        esc = html.escape(tok)
        if tok.startswith("//") or tok.startswith("/*") or tok.startswith("#") and language in {"python", "bash"}:
            cls = "c"
        elif tok.startswith(('"', "'")):
            cls = "s"
        elif re.fullmatch(r"\d+(?:\.\d+)?(?:e[+-]?\d+)?[uUlLfF]*", tok, re.I):
            cls = "mi"
        elif tok in CPP_KEYWORDS or tok in PY_KEYWORDS:
            cls = "k"
        elif tok in CPP_TYPES:
            cls = "kt"
        elif tok in CPP_BUILTINS:
            cls = "nb"
        elif re.fullmatch(r"[A-Za-z_]\w*", tok):
            # Function-like identifier.
            rest = line[m.end():]
            cls = "nf" if re.match(r"\s*\(", rest) else "n"
        elif re.fullmatch(r"[+\-*/%=<>!&|^~?:.,;(){}\[\]]+", tok):
            cls = "o" if tok.strip() not in "(){}[];,." else "p"
        else:
            cls = "n"
        out.append(f'<span class="{cls}">{esc}</span>')
        pos = m.end()
    out.append(html.escape(line[pos:]))
    return "".join(out)


def simple_highlight(code, language):
    return "\n".join(simple_highlight_line(line, language) for line in code.splitlines())


def render_code_block(code, language=""):
    code = code.rstrip("\n")
    lines = code.splitlines() or [""]
    compact = len(lines) <= 24

    # Use the fast built-in highlighter for print output so the DOM stays
    # pagination-friendly. Table-based line numbers looked nice on screen, but
    # browsers treat them as one large unbreakable box when printing.
    highlighted_lines = [simple_highlight_line(line, language) for line in lines]

    rows = []
    for idx in range(len(lines)):
        text_html = highlighted_lines[idx] if highlighted_lines[idx] else "&nbsp;"
        rows.append(
            '<div class="code-line">'
            f'<span class="code-text">{text_html}</span>'
            '</div>'
        )
    cls = "codehilite code-grid compact" if compact else "codehilite code-grid breakable"
    return f'<div class="{cls}">{"".join(rows)}</div>'


# ------------------------------
# Markdown table renderer
# ------------------------------

def split_table_row(line):
    """Split a Markdown table row while respecting escaped pipes and backticks."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]

    cells = []
    buf = []
    in_code = False
    escaped = False
    i = 0
    while i < len(s):
        ch = s[i]
        if escaped:
            # Keep the escaped character itself; "\\|" becomes a literal pipe.
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "`":
            in_code = not in_code
            buf.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if escaped:
        buf.append("\\")
    cells.append("".join(buf).strip())
    return cells


def parse_table_separator(line):
    cells = split_table_row(line)
    if not cells:
        return None
    aligns = []
    for cell in cells:
        c = cell.strip()
        if not re.fullmatch(r":?-{1,}:?", c):
            return None
        if c.startswith(":") and c.endswith(":"):
            aligns.append("center")
        elif c.startswith(":"):
            aligns.append("left")
        elif c.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("center")
    return aligns


def render_markdown_table(lines, start):
    """Render a GitHub-style Markdown table starting at `start`."""
    if start + 1 >= len(lines):
        return None, start

    header = split_table_row(lines[start])
    aligns = parse_table_separator(lines[start + 1])
    if aligns is None or not header:
        return None, start

    ncol = max(len(header), len(aligns))
    if len(header) < ncol:
        header += [""] * (ncol - len(header))
    elif len(aligns) < ncol:
        aligns += ["center"] * (ncol - len(aligns))

    rows = []
    i = start + 2
    while i < len(lines):
        s = lines[i].strip()
        if not s or "|" not in s:
            break
        cells = split_table_row(lines[i])
        if len(cells) > ncol:
            # Be permissive: extra cells are folded into the last column.
            cells = cells[:ncol - 1] + [" | ".join(cells[ncol - 1:])]
        if len(cells) < ncol:
            cells += [""] * (ncol - len(cells))
        rows.append(cells)
        i += 1

    def cell_html(text, align, tag):
        return f'<{tag} style="text-align:{align}">{render_inline(text)}</{tag}>'

    out = ['<table class="md-table">', '<thead><tr>']
    for text, align in zip(header, aligns):
        out.append(cell_html(text, align, "th"))
    out += ['</tr></thead>']

    if rows:
        out.append('<tbody>')
        for row in rows:
            out.append('<tr>')
            for text, align in zip(row, aligns):
                out.append(cell_html(text, align, "td"))
            out.append('</tr>')
        out.append('</tbody>')

    out.append('</table>')
    return "\n".join(out), i


# ------------------------------
# Markdown block renderer
# ------------------------------

def render_markdown_html(chapter):
    lines = chapter.content.splitlines()
    heading_iter = iter(chapter.headings)
    current_heading = next(heading_iter, None)
    blocks = []
    i = 0
    skipped_h1 = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        # H1 is rendered separately by build_html as the actual chapter title.
        m = re.match(r"^#\s+(.*\S)\s*$", line)
        if m and not skipped_h1:
            skipped_h1 = True
            i += 1
            continue

        # Markdown table.
        table_html, next_i = render_markdown_table(lines, i)
        if table_html is not None:
            blocks.append(table_html)
            i = next_i
            continue

        # Explicit HTML / page break blocks.
        if stripped.startswith("<") and stripped.endswith(">"):
            blocks.append(line)
            i += 1
            continue

        # Fenced code.
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            blocks.append(render_code_block("\n".join(lines[i + 1:j]), language))
            i = j + 1 if j < len(lines) else j
            continue

        # Display math $$ ... $$ -> MathJax \[ ... \].
        if stripped.startswith("$$"):
            if len(stripped) > 4 and stripped.endswith("$$"):
                tex = stripped[2:-2].strip()
                blocks.append(f'<div class="math-block">\\[{html.escape(tex)}\\]</div>')
                i += 1
                continue
            parts = [stripped[2:]]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.endswith("$$"):
                    parts.append(s[:-2])
                    i += 1
                    break
                parts.append(lines[i])
                i += 1
            tex = "\n".join(x for x in parts if x).strip()
            blocks.append(f'<div class="math-block">\\[{html.escape(tex)}\\]</div>')
            continue

        # Markdown headings.
        mh = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if mh:
            level = len(mh.group(1))
            text_value = mh.group(2).strip()
            if is_duplicate_chapter_heading(chapter, text_value):
                i += 1
                continue
            anchor = ""
            display_text = text_value
            marker = ""
            logical_level = level
            if current_heading and current_heading.level == level and current_heading.text == text_value:
                anchor = f' id="{current_heading.anchor}"'
                display_text = current_heading.display_text or text_value
                marker = current_heading.marker
                logical_level = current_heading.logical_level or level
                current_heading = next(heading_iter, None)
            marker_html = f'<span class="pdf-marker">{marker}</span>' if marker else ""
            html_level = min(6, max(2, logical_level))
            blocks.append(f'<h{html_level}{anchor}>{marker_html}{render_inline(display_text)}</h{html_level}>')
            i += 1
            continue

        # Lists (simple, suitable for this template book).
        if re.match(r"^[-*+]\s+", stripped):
            items = []
            while i < len(lines):
                s = lines[i].strip()
                mm = re.match(r"^[-*+]\s+(.*)$", s)
                if not mm:
                    break
                items.append(f'<li>{render_inline(mm.group(1))}</li>')
                i += 1
            blocks.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            items = []
            while i < len(lines):
                s = lines[i].strip()
                mm = re.match(r"^\d+[.)]\s+(.*)$", s)
                if not mm:
                    break
                items.append(f'<li>{render_inline(mm.group(1))}</li>')
                i += 1
            blocks.append("<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        # Blockquote.
        if stripped.startswith(">"):
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].lstrip())
                i += 1
            blocks.append(f'<blockquote>{render_inline(" ".join(q))}</blockquote>')
            continue

        # Paragraph.
        paragraph = [stripped]
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                i += 1
                break
            if re.match(r"^(#{1,6})\s+", s):
                break
            if s.startswith("```") or s.startswith("$$"):
                break
            if s.startswith("<") and s.endswith(">"):
                break
            if re.match(r"^[-*+]\s+", s) or re.match(r"^\d+[.)]\s+", s):
                break
            if s.startswith(">"):
                break
            if i + 1 < len(lines) and "|" in s and parse_table_separator(lines[i + 1]) is not None:
                break
            paragraph.append(s)
            i += 1
        blocks.append(f'<p>{render_inline(" ".join(paragraph))}</p>')

    return "\n".join(blocks)


# ------------------------------
# TOC
# ------------------------------

def render_toc_item(heading, page):
    display_text = heading.display_text or heading.text
    _, toc_text = split_existing_heading_number(display_text)
    level = getattr(heading, "logical_level", heading.level)
    return (
        f'<div class="toc-entry toc-level-{level}">'
        f'<a href="#{heading.anchor}"><span class="toc-name">{render_inline(toc_text)}</span>'
        f'<span class="toc-dots"></span><span class="toc-page">{page if page is not None else ""}</span></a>'
        f'</div>'
    )


def is_duplicate_chapter_heading(chapter, heading_text):
    t = normalize_search_text(heading_text)
    if not t:
        return True
    ct = normalize_search_text(chapter.title)
    if t == ct:
        return True
    if re.match(r"^第[0-9０-９一二三四五六七八九十百千万零〇两]+章", heading_text.strip()):
        return True
    return False


def render_toc_group(chapter, pages, depth, chapter_no):
    entries = [h for h in chapter.headings
               if h.level <= depth + 1 and not is_duplicate_chapter_heading(chapter, h.text)]
    items = ''.join(render_toc_item(heading, pages.get(heading.anchor)) for heading in entries)
    return (
        f'<div class="toc-category-inner"><span>{html.escape(chapter.title)}</span></div>'
        f'<div class="toc-entries">{items}</div>'
    )

def build_html(chapters, title, toc_depth, page_map=None, cover_image="", version="", author="", progress_label="render HTML"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page_map = page_map or {}
    progress_started = time.monotonic()

    cover_img_html = ""
    if cover_image:
        p = Path(cover_image).resolve()
        if p.exists():
            cover_img_html = f'<img class="cover-logo" src="{p.as_uri()}" alt="">'

    numbered = [c for c in chapters if not is_front_matter(c)]
    chapter_number = {id(c): i for i, c in enumerate(numbered, start=1)}

    groups = [
        render_toc_group(chapter, page_map, toc_depth, chapter_number_for(chapter, chapter_number[id(chapter)]))
        for chapter in numbered
    ]

    front_sections = []
    chapter_sections = []
    total_chapters = len(chapters)
    show_progress(progress_label, 0, total_chapters, progress_started)
    front_index = 0
    for i, chapter in enumerate(chapters, start=1):
        anchor = make_anchor(chapter.title, {})
        if is_front_matter(chapter):
            front_index += 1
            front_sections.append(
                f'<section class="front-matter" id="{anchor}">'
                + ('<div class="front-matter-title">前言</div>' if front_index == 1 else '')
                + f'<div class="chapter-body">{render_markdown_html(chapter)}</div>'
                '</section>'
            )
        else:
            n = chapter_number_for(chapter, chapter_number[id(chapter)])
            # No large chapter title on the first body page; only the running header is shown.
            marker = f'WZCHAPTER-{n}'
            chapter_sections.append(
                f'<section class="chapter" id="{anchor}" data-chapter-index="{n}">'
                f'<span class="pdf-marker pdf-chapter-marker">{marker}</span>'
                f'<div class="chapter-title">{render_inline(chapter_body_title(chapter, chapter_number[id(chapter)]))}</div>'
                f'<div class="chapter-body">{render_markdown_html(chapter)}</div>'
                '</section>'
            )
        show_progress(progress_label, i, total_chapters, progress_started)
    print(flush=True)

    highlighter_text = "Pygments" if PYGMENTS_OK else "内置高亮"
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<style>
@page {{
  size: A4;
  margin: 16mm 20mm 16mm 20mm;
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #fff; }}
body {{
  color: #2b2b2b;
  font-family: "Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", sans-serif;
  font-size: 14.2pt;
  line-height: 1.58;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}

p, li {{ orphans: 3; widows: 3; }}
p {{ margin: 2.3mm 0; text-align: justify; text-justify: inter-ideograph; word-break: break-word; }}
strong {{ font-weight: 800; }}
mark {{ background: #fff000; padding: 0 .08em; }}
a {{ color: inherit; text-decoration: none; }}

/* Front cover: clean, book-like, visually similar to the reference. */
.cover {{
  height: 249mm;
  break-after: page;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}}
.cover-logo {{ max-width: 70mm; max-height: 52mm; object-fit: contain; margin-bottom: 7mm; }}
.cover-rule {{ width: 90mm; border-top: 2px solid #111; margin: 4mm auto 9mm; }}
.cover-brand {{ font-family: Georgia, "Times New Roman", serif; font-size: 22pt; font-weight: 700; margin-bottom: 3mm; }}
.cover-title {{ font-family: Georgia, "Times New Roman", serif; font-size: 28pt; font-weight: 700; line-height: 1.2; }}
.cover-meta {{ margin-top: 70mm; font-family: Georgia, "Times New Roman", serif; font-size: 14pt; font-weight: 700; line-height: 1.55; }}
.cover-meta div:empty {{ display: none; }}

/* TOC */
.toc {{ break-after: page; font-family: "SimSun", "Songti SC", "Noto Serif CJK SC", serif; }}
.toc h2 {{
  margin: 0 0 8mm;
  text-align: center;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  font-size: 27pt;
  line-height: 1;
  font-weight: 700;
}}
.toc-body {{
  position: relative;
  column-count: 2;
  column-gap: 4.4mm;
  column-fill: balance;
  column-rule: 1px solid #333;
  min-height: 252mm;
}}
.toc-entries {{
  margin: 0;
}}
.toc-category-inner {{
  position: relative;
  display: flex;
  align-items: center;
  min-height: 11.8mm;
  padding: 1.05mm 1.4mm;
  margin: 6mm 0 4.5mm;
  background: #e8e8e8;
  font-weight: 700;
  font-size: 13.5pt;
  line-height: 1.32;
  break-after: avoid;
  page-break-after: avoid;
  -webkit-column-span: all;
  column-span: all;
}}
.toc-entry {{
  margin: 0;
  line-height: 1.22;
  font-size: 13.1pt;
  break-inside: avoid;
  page-break-inside: avoid;
}}
.toc-entry a {{ display: flex; width: 100%; align-items: baseline; }}
.toc-name {{ flex: 0 1 auto; white-space: normal; }}
.toc-dots {{ flex: 1 1 auto; min-width: 2mm; margin: 0 1mm; border-bottom: 1px dotted #777; transform: translateY(-.17em); }}
.toc-page {{ flex: 0 0 auto; min-width: 4mm; text-align: right; }}
.toc-level-3 .toc-name {{ padding-left: 4mm; }}
.toc-level-4 .toc-name {{ padding-left: 8mm; }}
.toc-level-5 .toc-name {{ padding-left: 12mm; }}
.toc-level-6 .toc-name {{ padding-left: 16mm; }}

/* Invisible deterministic PDF markers used only for pagination calibration. */
.pdf-marker {{
  display: inline;
  font-size: 0.1pt;
  line-height: 0;
  color: #fff;
  white-space: nowrap;
  margin: 0;
  padding: 0;
}}

/* Actual content */
.chapter {{ break-before: page; }}
.chapter:first-of-type {{ break-before: auto; }}
.front-matter {{ break-before: page; break-after: page; }}
.front-matter-title {{
  margin: 0 0 8mm;
  text-align: center;
  font-family: "STKaiti", "KaiTi", "SimSun", serif;
  font-size: 27pt;
  line-height: 1;
  font-weight: 700;
}}
.chapter-title {{
  margin: 0 0 8mm;
  text-align: center;
  font-size: 21pt;
  line-height: 1.2;
  font-weight: 800;
  break-after: avoid;
}}
.chapter > h1 {{
  margin: 0 0 7mm;
  font-size: 21pt;
  line-height: 1.2;
  font-weight: 800;
  break-after: avoid;
}}
.chapter-body h2 {{
  margin: 4.5mm 0 2.5mm;
  font-size: 17.2pt;
  line-height: 1.25;
  font-weight: 800;
  break-after: avoid;
}}
.chapter-body h3 {{
  margin: 3.8mm 0 2mm;
  font-size: 14.5pt;
  line-height: 1.3;
  font-weight: 800;
  break-after: avoid;
}}
.chapter-body h4, .chapter-body h5, .chapter-body h6 {{
  margin: 3mm 0 1.7mm;
  font-size: 12.5pt;
  font-weight: 800;
  break-after: avoid;
}}

.inline-code {{
  display: inline-block;
  padding: 0 .25em;
  border: 1px solid #dcdfe2;
  border-radius: 2px;
  background: #f1f2f3;
  font-family: "Consolas", "Cascadia Mono", "Noto Sans Mono CJK SC", monospace;
  font-size: .88em;
  line-height: 1.15;
  white-space: nowrap;
}}

/* Markdown tables */
.md-table {{
  width: 100%;
  margin: 4mm 0 5mm;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 9.6pt;
  line-height: 1.45;
  break-inside: avoid;
  page-break-inside: avoid;
}}
.md-table th, .md-table td {{
  padding: 1.7mm 1.8mm;
  border: 1px solid #cfcfcf;
  vertical-align: middle;
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.md-table thead th {{
  background: #f0f0f0;
  font-weight: 800;
}}
.md-table tbody tr:nth-child(even) td {{ background: #fafafa; }}

/* Code block geometry is intentionally close to the reference PDF. */
.codehilite {{
  width: 100%;
  margin: 2.1mm 0 3mm;
  border: 1px solid #dadde0;
  border-radius: 3px;
  background: #f6f6f6;
  overflow: visible;
}}
.codehilite.compact {{
  break-inside: avoid;
  page-break-inside: avoid;
}}
.codehilite.breakable {{
  break-inside: auto;
  page-break-inside: auto;
}}
.code-line {{
  display: block;
  break-inside: auto;
  page-break-inside: auto;
}}
.code-text {{
  display: block;
  margin: 0;
  font-family: "Consolas", "Cascadia Mono", "DejaVu Sans Mono", monospace;
  font-size: 13.1pt;
  line-height: 1.0;
  tab-size: 4;
  padding: 0.12mm 0.8mm 0.12mm 0.8mm;
  white-space: pre;
  overflow-wrap: normal;
  word-break: normal;
}}

/* Pygments + built-in fallback palette, tuned to the sample. */
.codehilite .k, .codehilite .kd, .codehilite .kn, .codehilite .kp, .codehilite .kr, .codehilite .kc {{ color: #8b168d; }}
.codehilite .kt {{ color: #14855b; }}
.codehilite .nf, .codehilite .fm {{ color: #001dff; }}
.codehilite .nc, .codehilite .nn, .codehilite .nd {{ color: #14855b; }}
.codehilite .mi, .codehilite .mf, .codehilite .mh, .codehilite .mb, .codehilite .m {{ color: #14855b; }}
.codehilite .c, .codehilite .ch, .codehilite .cm {{ color: #b76800; }}
.codehilite .cp, .codehilite .cpf {{ color: #333; }}
.codehilite .o {{ color: #c12828; }}
.codehilite .s, .codehilite .sa, .codehilite .sb, .codehilite .sc, .codehilite .dl, .codehilite .sd, .codehilite .se, .codehilite .sh, .codehilite .si, .codehilite .sx {{ color: #008000; }}
.codehilite .nb {{ color: #006f4c; }}
.codehilite .p, .codehilite .n, .codehilite .w {{ color: #222; }}
.codehilite .na {{ color: #1c5a9c; }}

ul, ol {{ margin: 2.5mm 0 3mm; padding-left: 7mm; }}
li {{ margin: 1mm 0; }}
blockquote {{ margin: 3mm 0; padding-left: 3mm; border-left: 1.5px solid #d5d5d5; color: #555; }}
.math-block {{ margin: 4mm 0; text-align: center; overflow-x: auto; }}
.inline-image, img:not(.cover-logo) {{ display: block; max-width: 100%; height: auto; margin: 3mm auto; }}
hr {{ border: 0; border-top: 1px solid #ddd; margin: 5mm 0; }}

.page-break {{ break-before: page; height: 0; }}
.no-break {{ break-inside: avoid; page-break-inside: avoid; }}

@media screen {{
  body {{ max-width: 1000px; margin: 0 auto; padding: 32px 44px 80px; font-size: 16px; }}
  .cover, .toc {{ min-height: 1080px; }}
  .codehilite {{ box-shadow: 0 1px 3px rgba(0,0,0,.04); }}
}}
</style>
</head>
<body>
<section class="cover">
  {cover_img_html}
  <div class="cover-rule"></div>
  <div class="cover-brand">{html.escape(title)}</div>
  <div class="cover-title">Algorithm Template</div>
  <div class="cover-meta">
    <div>{html.escape(version)}</div>
    <div>{html.escape(author)}</div>
  </div>
</section>

{''.join(front_sections)}

<section class="toc">
  <span class="pdf-marker">WZTOC</span>
  <h2>目录</h2>
  <div class="toc-body">{''.join(groups)}</div>
</section>

{''.join(chapter_sections)}
</body>
</html>
'''


# ------------------------------
# Browser / PDF
# ------------------------------

def find_browser(browser_arg):
    candidates = []
    if browser_arg:
        candidates.append(Path(browser_arg))
    for name in ["chrome", "msedge", "chromium", "chromium-browser", "google-chrome", "microsoft-edge"]:
        p = shutil.which(name)
        if p:
            candidates.append(Path(p))
    local = Path.home() / "AppData" / "Local"
    candidates += [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        local / "Google" / "Chrome" / "Application" / "chrome.exe",
        local / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path("/usr/bin/google-chrome"), Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"), Path("/usr/bin/microsoft-edge"),
    ]
    seen = set()
    for p in candidates:
        k = str(p).lower()
        if k in seen:
            continue
        seen.add(k)
        if p.exists():
            return p
    return None


def export_pdf(html_path, pdf_path, browser_path=None, pass_label="PDF export", timeout=600):
    """Export through Playwright PDF API.

    A tiny localhost server is used instead of a file:// URL. Browser-native
    print headers/footers are explicitly disabled, so no date/title/URL is
    ever added by the browser.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for PDF export: python -m pip install playwright") from exc

    started_at = time.monotonic()
    root = ROOT.resolve()
    html_path = html_path.resolve()
    pdf_path = pdf_path.resolve()
    try:
        rel_url = html_path.relative_to(root).as_posix()
    except ValueError:
        raise RuntimeError(f"HTML output must be inside project root: {html_path}")

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/{rel_url}"

    print(f"[book-builder] {pass_label}: starting Playwright PDF export (browser headers/footers disabled)", flush=True)
    with sync_playwright() as pw:
        browser = None
        try:
            launch_kwargs = {"headless": True}
            if browser_path is not None:
                launch_kwargs["executable_path"] = str(browser_path)
            browser = pw.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            timeout_ms = 0 if not timeout else timeout * 1000
            page.goto(url, wait_until="load", timeout=timeout_ms)
            try:
                page.wait_for_function("document.fonts && document.fonts.status === 'loaded'", timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(800)
            print(f"[book-builder] {pass_label}: printing A4 PDF...", flush=True)
            page.pdf(
                path=str(pdf_path),
                width="210mm",
                height="297mm",
                print_background=True,
                display_header_footer=False,
                prefer_css_page_size=False,
                margin={"top": "16mm", "right": "20mm", "bottom": "16mm", "left": "20mm"},
            )
            elapsed = format_elapsed(time.monotonic() - started_at)
            if fitz is not None and pdf_path.exists():
                with fitz.open(pdf_path) as check_doc:
                    size = check_doc[0].rect
                    print(f"[book-builder] {pass_label}: finished in {elapsed} | A4 page {size.width:.1f} x {size.height:.1f} pt", flush=True)
            else:
                print(f"[book-builder] {pass_label}: finished in {elapsed}", flush=True)
        finally:
            if browser is not None:
                browser.close()
            server.shutdown()
            server.server_close()


# ------------------------------
# PDF inspection / post processing
# ------------------------------

def normalize_search_text(s):
    return re.sub(r"\s+", "", s or "")


def search_marker_page(doc, marker, start_page=0, last_page=None):
    if not marker:
        return None
    if last_page is None:
        last_page = len(doc)
    for pno in range(max(0, start_page), min(len(doc), last_page)):
        if doc[pno].search_for(marker):
            return pno
        txt = doc[pno].get_text("text") or ""
        if marker in txt:
            return pno
    return None


def build_page_map(pdf_path, chapters):
    if fitz is None:
        raise RuntimeError("TOC page numbers/header/footer require PyMuPDF: pip install pymupdf")
    numbered = [c for c in chapters if not is_front_matter(c)]
    doc = fitz.open(pdf_path)

    # Deterministic chapter markers eliminate collisions with duplicate heading text in the TOC/body.
    chapter_pages = []
    started_at = time.monotonic()
    print(f"[book-builder] locating chapter starts: 0/{len(numbered)}", end="", flush=True)
    cursor = 0
    for idx, chapter in enumerate(numbered, start=1):
        marker = f"WZCHAPTER-{chapter_number_for(chapter, idx)}"
        p = search_marker_page(doc, marker, cursor)
        chapter_pages.append(p)
        if p is not None:
            cursor = p
        print(f"\r[book-builder] locating chapter starts: {idx}/{len(numbered)} ({format_elapsed(time.monotonic()-started_at)})", end="", flush=True)
    print(flush=True)

    first_content_page = next((p for p in chapter_pages if p is not None), None)
    if first_content_page is None:
        doc.close()
        raise RuntimeError("cannot locate the first chapter marker in the preliminary PDF")
    toc_start_page = search_marker_page(doc, "WZTOC", 0, first_content_page)

    heading_started_at = time.monotonic()
    page_map = {}
    toc_entries = []
    for chapter in numbered:
        toc_entries.extend([h for h in chapter.headings if not is_duplicate_chapter_heading(chapter, h.text)])
    total_headings = len(toc_entries)
    done = 0
    print(f"[book-builder] locating TOC headings: 0/{total_headings}", end="", flush=True)

    for cidx, chapter in enumerate(numbered):
        cp = chapter_pages[cidx]
        if cp is None:
            done += sum(1 for h in chapter.headings if not is_duplicate_chapter_heading(chapter, h.text))
            continue
        next_cp = next((x for x in chapter_pages[cidx + 1:] if x is not None and x > cp), None)
        end_page = next_cp if next_cp is not None else len(doc)
        cursor = cp
        for heading in chapter.headings:
            if is_duplicate_chapter_heading(chapter, heading.text):
                continue
            hp = search_marker_page(doc, heading.marker, cursor, end_page)
            if hp is not None:
                page_map_val = hp - first_content_page + 1
                # Keep the first actual occurrence inside this chapter window.
                page_map[heading.anchor] = page_map_val
                cursor = hp
            done += 1
            if done == total_headings or done % max(1, total_headings // 80) == 0:
                print(f"\r[book-builder] locating TOC headings: {done}/{total_headings} ({format_elapsed(time.monotonic()-heading_started_at)})", end="", flush=True)
    print(flush=True)
    doc.close()
    return page_map, first_content_page, chapter_pages, toc_start_page


def page_insert_text(page, rect, text, fontsize, align=1):
    # PyMuPDF provides built-in CJK fonts; using china-s avoids depending on a
    # particular Windows font file and prevents Chinese header/footer glyphs
    # from becoming question marks.
    page.insert_textbox(
        rect, text, fontname="china-s", fontsize=fontsize,
        color=(0, 0, 0), align=align,
    )


def add_headers_footers(pdf_path, chapters, first_content_page, chapter_starts, toc_start_page=None):
    if fitz is None:
        return

    numbered = [c for c in chapters if not is_front_matter(c)]
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    started_at = time.monotonic()

    chapter_starts = list(chapter_starts or [])
    valid_starts = [p for p in chapter_starts if p is not None]
    if valid_starts:
        first_content_page = min(valid_starts)

    print(
        f"[book-builder] header/footer: writing {total_pages} pages "
        f"(first content PDF page {first_content_page + 1})",
        flush=True,
    )

    page_chapter = [0] * total_pages
    current = 0
    for pno in range(total_pages):
        while current + 1 < len(chapter_starts):
            nxt = chapter_starts[current + 1]
            if nxt is None or nxt > pno:
                break
            current += 1
        page_chapter[pno] = current

    report_every = max(1, total_pages // 50)
    for pno, page in enumerate(doc):
        w, h = page.rect.width, page.rect.height
        if pno == 0:
            pass
        elif pno < first_content_page:
            if toc_start_page is not None and pno >= toc_start_page:
                page_insert_text(page, fitz.Rect(0, h - 28, w, h - 8), f"目录 - {pno - toc_start_page + 1}", 8.7, 1)
        elif numbered:
            idx = min(page_chapter[pno], len(numbered) - 1)
            header = chapter_header_title(numbered[idx], idx + 1)
            page_insert_text(page, fitz.Rect(0, 18, w, 34), header, 8.8, 1)
            printed_num = pno - first_content_page + 1
            page_insert_text(page, fitz.Rect(0, h - 28, w, h - 8), str(printed_num), 8.8, 1)

        done = pno + 1
        if done == total_pages or done % report_every == 0:
            print(
                f"\r[book-builder] header/footer: {done}/{total_pages} "
                f"({done / total_pages:.1%}) | elapsed {format_elapsed(time.monotonic() - started_at)}",
                end="", flush=True,
            )
    print(flush=True)

    print("[book-builder] header/footer: saving PDF (incremental update)...", flush=True)
    save_started = time.monotonic()
    try:
        # We only appended header/footer annotations to an already valid PDF.
        # An incremental save avoids rebuilding/compressing the entire document,
        # which is what made the previous garbage=4 full save take a very long time.
        doc.saveIncr()
        doc.close()
        print(
            f"[book-builder] header/footer: incremental save finished in "
            f"{format_elapsed(time.monotonic() - save_started)} "
            f"(total {format_elapsed(time.monotonic() - started_at)})", flush=True
        )
        return
    except Exception as exc:
        print(
            f"[book-builder] header/footer: incremental save failed: {exc}",
            flush=True,
        )

    # Fallback: reopen the file and use a lightweight full save. Do not use
    # garbage=4/deflate=True here; both can force an expensive whole-document
    # rebuild on a large book.
    try:
        doc.close()
    except Exception:
        pass
    print("[book-builder] header/footer: fallback full save (no garbage collection)...", flush=True)
    save_started = time.monotonic()
    doc = fitz.open(pdf_path)
    tmp = pdf_path.with_suffix(".tmp.pdf")
    if tmp.exists():
        tmp.unlink()
    # The annotations/text are already present in the in-memory document only,
    # so recreate them before the fallback save. This path should be rare.
    page_chapter = [0] * total_pages
    current = 0
    for pno in range(total_pages):
        while current + 1 < len(chapter_starts):
            nxt = chapter_starts[current + 1]
            if nxt is None or nxt > pno:
                break
            current += 1
        page_chapter[pno] = current
    for pno, page in enumerate(doc):
        w, h = page.rect.width, page.rect.height
        if pno == 0:
            continue
        if pno < first_content_page:
            page_insert_text(page, fitz.Rect(0, h - 28, w, h - 8), f"目录 - {pno}", 8.7, 1)
        elif numbered:
            idx = min(page_chapter[pno], len(numbered) - 1)
            header = chapter_header_title(numbered[idx], idx + 1)
            page_insert_text(page, fitz.Rect(0, 18, w, 34), header, 8.8, 1)
            printed_num = pno - first_content_page + 1
            page_insert_text(page, fitz.Rect(0, h - 28, w, h - 8), str(printed_num), 8.8, 1)
    doc.save(tmp, garbage=0, deflate=False, clean=False)
    doc.close()
    tmp.replace(pdf_path)
    print(
        f"[book-builder] header/footer: fallback save finished in "
        f"{format_elapsed(time.monotonic() - save_started)} "
        f"(total {format_elapsed(time.monotonic() - started_at)})", flush=True
    )

def patch_toc_page_numbers(html_path, chapters, title, toc_depth, cover_image, version, author, browser_path, output_pdf, pdf_timeout=600):
    run_tag = str(time.time_ns())
    phase1_pdf = output_pdf.with_name(output_pdf.stem + f".{run_tag}.phase1.pdf")
    phase2_pdf = output_pdf.with_name(output_pdf.stem + f".{run_tag}.phase2.pdf")
    phase3_pdf = output_pdf.with_name(output_pdf.stem + f".{run_tag}.phase3.pdf")

    for path in (phase1_pdf, phase2_pdf, phase3_pdf):
        if path.exists():
            path.unlink()

    # Pass 1: body pagination without TOC page numbers.
    print("[book-builder] phase 1/3: rendering preliminary HTML...", flush=True)
    html_path.write_text(
        build_html(chapters, title, toc_depth, {}, cover_image, version, author, progress_label="render HTML #1"),
        encoding="utf-8",
    )
    print("[book-builder] phase 1/3: exporting preliminary PDF...", flush=True)
    export_pdf(html_path, phase1_pdf, browser_path, pass_label="PDF #1/3", timeout=pdf_timeout)

    print("[book-builder] phase 1/3: locating headings and page numbers...", flush=True)
    page_map, first_content_page, chapter_starts, toc_start_page = build_page_map(phase1_pdf, chapters)

    # Pass 2: inject page numbers into TOC and export again.
    print("[book-builder] phase 2/3: rendering calibrated HTML...", flush=True)
    html_path.write_text(
        build_html(chapters, title, toc_depth, page_map, cover_image, version, author, progress_label="render HTML #2"),
        encoding="utf-8",
    )
    print("[book-builder] phase 2/3: exporting calibrated PDF...", flush=True)
    export_pdf(html_path, phase2_pdf, browser_path, pass_label="PDF #2/3", timeout=pdf_timeout)

    # If TOC pagination changed, one final pass recalibrates.
    print("[book-builder] phase 3/3: verifying pagination...", flush=True)
    final_pdf = phase2_pdf
    page_map2, first_content_page2, chapter_starts2, toc_start_page2 = build_page_map(phase2_pdf, chapters)
    if page_map2 != page_map or first_content_page2 != first_content_page:
        print("[book-builder] phase 3/3: pagination changed; rendering final HTML...", flush=True)
        html_path.write_text(
            build_html(chapters, title, toc_depth, page_map2, cover_image, version, author, progress_label="render HTML #3"),
            encoding="utf-8",
        )
        export_pdf(html_path, phase3_pdf, browser_path, pass_label="PDF #3/3", timeout=pdf_timeout)
        final_pdf = phase3_pdf
        first_content_page = first_content_page2
        chapter_starts = chapter_starts2
        toc_start_page = toc_start_page2
    else:
        print("[book-builder] phase 3/3: pagination is stable; skipping final export.", flush=True)

    if output_pdf.exists():
        output_pdf.unlink()
    shutil.copyfile(final_pdf, output_pdf)
    print("[book-builder] finalizing header/footer...", flush=True)
    add_headers_footers(output_pdf, chapters, first_content_page, chapter_starts, toc_start_page)

    for path in (phase1_pdf, phase2_pdf, phase3_pdf):
        if path.exists():
            path.unlink()


# ------------------------------
# Main
# ------------------------------

def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check optional dependencies and warn if missing
    missing_deps = check_dependencies()
    if missing_deps:
        for dep in missing_deps:
            print(f"[book-builder] warning: {dep}", file=sys.stderr)

    chapters = discover_chapters()
    collect_headings(chapters)

    markdown_path = output_dir / f"{args.title}.md"
    html_path = output_dir / f"{args.title}.html"
    pdf_path = output_dir / f"{args.title}.pdf"

    # Preserve the merged Markdown export, but keep the logical chapter model
    # consistent with the PDF TOC (including A/B merging and duplicate-title filtering).
    md_parts = [f"# {args.title}", ""]
    for chapter in [c for c in chapters if is_front_matter(c)]:
        md_parts.extend([f"<!-- source: {chapter.path.as_posix()} -->", "", chapter.content.strip(), ""])
    md_parts.extend(["## 目录", ""])
    for chapter in [c for c in chapters if not is_front_matter(c)]:
        md_parts.append(f"### {chapter.title}")
        for heading in chapter.headings:
            if heading.level <= args.toc_depth + 1 and not is_duplicate_chapter_heading(chapter, heading.text):
                md_parts.append("    " * max(heading.level - 2, 0) + f"- {heading.display_text or heading.text}")
        md_parts.append("")
    for chapter in [c for c in chapters if not is_front_matter(c)]:
        md_parts.extend([f"<!-- source: {chapter.path.as_posix()} -->", "", chapter.content.strip(), ""])
    markdown_path.write_text("\n".join(md_parts).strip() + "\n", encoding="utf-8")
    print("[book-builder] preparing initial HTML...", flush=True)
    html_path.write_text(
        build_html(chapters, args.title, args.toc_depth, {}, args.cover_image, args.version, args.author, progress_label="initial HTML"),
        encoding="utf-8",
    )

    print(f"[book-builder] markdown: {markdown_path}")
    print(f"[book-builder] html: {html_path}")
    print(f"[book-builder] syntax highlighting: {'Pygments' if PYGMENTS_OK else 'built-in (fast regex)'}")
    if not PYGMENTS_OK:
        print("[book-builder] hint: pip install Pygments for richer language support; built-in mode is still supported.", flush=True)

    if args.pdf:
        if fitz is None:
            raise RuntimeError("PDF pagination/header/footer requires PyMuPDF. Run: python -m pip install pymupdf")
        browser_path = find_browser(args.browser)
        if browser_path is None:
            raise RuntimeError(
                "cannot find a supported browser for pdf export. "
                "Please install Microsoft Edge or Google Chrome, or pass --browser with the executable path."
            )
        cover_image = args.cover_image
        if not cover_image:
            for candidate in COVER_IMAGE_CANDIDATES:
                if candidate.exists():
                    cover_image = str(candidate)
                    break
        patch_toc_page_numbers(
            html_path, chapters, args.title, args.toc_depth,
            cover_image, args.version, args.author,
            browser_path, pdf_path, args.pdf_timeout,
        )
        print("[book-builder] toc: calibrated page numbers")
        print("[book-builder] header/footer: calibrated by PDF page positions")
        print(f"[book-builder] pdf: {pdf_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[book-builder] error: {exc}", file=sys.stderr)
        sys.exit(1)
