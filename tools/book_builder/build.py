import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "正文"
DEFAULT_OUTPUT_DIR = ROOT / "dist" / "book"
PROJECT_TITLE = "Wangzai_XCPC_Templete"


@dataclass
class Heading:
    level: int
    text: str
    anchor: str


@dataclass
class Chapter:
    path: Path
    title: str
    content: str
    headings: list[Heading] = field(default_factory=list)


def parse_args():
    parser = argparse.ArgumentParser(description="Build merged markdown/html/pdf for the template book.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="output directory for generated files")
    parser.add_argument("--title", default=PROJECT_TITLE, help="book title")
    parser.add_argument("--toc-depth", type=int, default=2, help="toc depth counted from chapter headings")
    parser.add_argument("--pdf", action="store_true", help="also export a printable PDF")
    parser.add_argument("--browser", default="", help="browser executable path used for headless PDF export")
    return parser.parse_args()


def discover_chapters():
    chapters = []
    for path in sorted(BOOK_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8").replace("\ufeff", "").strip() + "\n"
        title = path.stem
        for line in content.splitlines():
            match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if match:
                title = match.group(2).strip()
                break
        chapters.append(Chapter(path=path, title=title, content=content))
    if not chapters:
        raise RuntimeError(f"cannot find markdown chapters under: {BOOK_DIR}")
    return chapters


def make_anchor(text, used):
    base = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", text, flags=re.UNICODE).strip().lower()
    base = re.sub(r"\s+", "-", base)
    if not base:
        base = "section"
    count = used.get(base, 0)
    used[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def collect_headings(chapters):
    used = {}
    for chapter in chapters:
        chapter.headings.clear()
        for line in chapter.content.splitlines():
            match = re.match(r"^(#{2,6})\s+(.*\S)\s*$", line)
            if not match:
                continue
            chapter.headings.append(
                Heading(
                    level=len(match.group(1)),
                    text=match.group(2).strip(),
                    anchor=make_anchor(match.group(2).strip(), used),
                )
            )


def markdown_toc(chapters, toc_depth):
    lines = ["## 目录", ""]
    max_heading_level = toc_depth + 1
    for chapter in chapters:
        for heading in chapter.headings:
            if heading.level > max_heading_level:
                continue
            indent = "    " * max(heading.level - 2, 0)
            lines.append(f"{indent}- {heading.text}")
    lines.append("")
    return "\n".join(lines)


def build_markdown(chapters, title, toc_depth):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        f"# {title}",
        "",
        f"> 自动生成时间：{now}",
        "",
        markdown_toc(chapters, toc_depth),
    ]
    for chapter in chapters:
        parts.append(f"<!-- source: {chapter.path.as_posix()} -->")
        parts.append("")
        parts.append(chapter.content.strip())
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def render_inline(text):
    result = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j != -1:
                result.append(f"<code>{html.escape(text[i + 1:j])}</code>")
                i = j + 1
                continue
        link = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
        if link:
            label, url = link.groups()
            result.append(f"<a href=\"{html.escape(url, quote=True)}\">{html.escape(label)}</a>")
            i += link.end()
            continue
        result.append(html.escape(text[i]))
        i += 1
    return "".join(result)


def render_markdown_html(chapter):
    lines = chapter.content.splitlines()
    heading_iter = iter(chapter.headings)
    current_heading = next(heading_iter, None)
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Keep block HTML as-is so manual page breaks and custom tags still work.
        if stripped.startswith("<") and stripped.endswith(">"):
            blocks.append(line)
            i += 1
            continue

        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            cls = f" class=\"language-{html.escape(language)}\"" if language else ""
            blocks.append(f"<pre><code{cls}>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        if stripped.startswith("$$"):
            if len(stripped) > 4 and stripped.endswith("$$"):
                tex = stripped[2:-2].strip()
                blocks.append(f"<div class=\"math-block\">$$\n{html.escape(tex)}\n$$</div>")
                i += 1
                continue
            math_lines = [stripped[2:]]
            i += 1
            while i < len(lines):
                math_line = lines[i].strip()
                if math_line.endswith("$$"):
                    math_lines.append(math_line[:-2])
                    i += 1
                    break
                math_lines.append(lines[i])
                i += 1
            tex = "\n".join(part for part in math_lines if part).strip()
            blocks.append(f"<div class=\"math-block\">$$\n{html.escape(tex)}\n$$</div>")
            continue

        match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            anchor = ""
            if current_heading and current_heading.level == level and current_heading.text == text:
                anchor = f" id=\"{current_heading.anchor}\""
                current_heading = next(heading_iter, None)
            blocks.append(f"<h{level}{anchor}>{render_inline(text)}</h{level}>")
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,})", stripped):
            blocks.append("<hr />")
            i += 1
            continue

        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        if bullet:
            items = []
            while i < len(lines):
                item_line = lines[i].strip()
                item_match = re.match(r"^[-*+]\s+(.*)$", item_line)
                if not item_match:
                    break
                items.append(f"<li>{render_inline(item_match.group(1).strip())}</li>")
                i += 1
            blocks.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered:
            items = []
            while i < len(lines):
                item_line = lines[i].strip()
                item_match = re.match(r"^\d+\.\s+(.*)$", item_line)
                if not item_match:
                    break
                items.append(f"<li>{render_inline(item_match.group(1).strip())}</li>")
                i += 1
            blocks.append("<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        paragraph = [stripped]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                i += 1
                break
            if re.match(r"^(#{1,6})\s+", next_line) or next_line.startswith("```"):
                break
            if next_line.startswith("<") and next_line.endswith(">"):
                break
            if next_line.startswith("$$"):
                break
            if re.match(r"^[-*+]\s+", next_line) or re.match(r"^\d+\.\s+", next_line):
                break
            if re.fullmatch(r"(-{3,}|\*{3,})", next_line):
                break
            paragraph.append(next_line)
            i += 1
        blocks.append(f"<p>{render_inline(' '.join(paragraph))}</p>")

    return "\n".join(blocks)


def build_html_toc(chapters, toc_depth):
    max_heading_level = toc_depth + 1
    items = []
    for chapter in chapters:
        for heading in chapter.headings:
            if heading.level > max_heading_level:
                continue
            cls = f"toc-level-{heading.level}"
            items.append(
                f"<li class=\"{cls}\"><a href=\"#{heading.anchor}\">{html.escape(heading.text)}</a></li>"
            )
    return "<ul class=\"toc-list\">\n" + "\n".join(items) + "\n</ul>"


def build_html(chapters, title, toc_depth):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chapter_html = []
    for chapter in chapters:
        chapter_html.append(
            "<section class=\"chapter\">\n"
            f"{render_markdown_html(chapter)}\n"
            "</section>"
        )
    toc_html = build_html_toc(chapters, toc_depth)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  }},
  svg: {{
    fontCache: 'global'
  }}
}};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<style>
@page {{
  size: A4;
  margin: 18mm 14mm 18mm 16mm;
}}
body {{
  color: #111;
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  font-size: 12px;
  line-height: 1.65;
  margin: 0 auto;
  max-width: 180mm;
}}
h1, h2, h3, h4, h5, h6 {{
  color: #111;
  line-height: 1.3;
}}
h1 {{
  font-size: 28px;
  text-align: center;
  margin-top: 36mm;
  margin-bottom: 8mm;
}}
h2 {{
  font-size: 20px;
  margin-top: 12mm;
  border-bottom: 1px solid #ddd;
  padding-bottom: 2mm;
}}
h3 {{
  font-size: 16px;
  margin-top: 8mm;
}}
h4, h5, h6 {{
  font-size: 14px;
  margin-top: 6mm;
}}
p, li {{
  word-break: break-word;
}}
pre {{
  background: #f6f8fa;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  font-family: "Cascadia Code", "Consolas", monospace;
  font-size: 10.5px;
  line-height: 1.45;
  overflow-wrap: anywhere;
  padding: 10px 12px;
  white-space: pre-wrap;
}}
code {{
  background: #f6f8fa;
  border-radius: 4px;
  font-family: "Cascadia Code", "Consolas", monospace;
  padding: 1px 4px;
}}
pre code {{
  background: transparent;
  padding: 0;
}}
.title-page {{
  min-height: 240mm;
}}
.meta {{
  color: #666;
  text-align: center;
}}
.toc {{
  break-before: page;
}}
.toc-list {{
  list-style: none;
  padding-left: 0;
}}
.toc-list li {{
  margin: 3px 0;
}}
.toc-level-3 {{
  padding-left: 1.2em;
}}
.toc-level-4 {{
  padding-left: 2.4em;
}}
.toc-level-5 {{
  padding-left: 3.6em;
}}
.chapter {{
  break-before: page;
}}
.chapter:first-of-type {{
  break-before: auto;
}}
.math-block {{
  margin: 8px 0;
  overflow-x: auto;
}}
a {{
  color: inherit;
  text-decoration: none;
}}
</style>
</head>
<body>
  <section class="title-page">
    <h1>{html.escape(title)}</h1>
    <p class="meta">自动生成时间：{html.escape(now)}</p>
  </section>
  <section class="toc">
    <h2>目录</h2>
    {toc_html}
  </section>
  {"".join(chapter_html)}
</body>
</html>
"""


def find_browser(browser_arg):
    candidates = []
    if browser_arg:
        candidates.append(Path(browser_arg))
    which_candidates = [
        "chrome",
        "msedge",
        "chromium",
        "chromium-browser",
        "google-chrome",
        "microsoft-edge",
    ]
    for name in which_candidates:
        path = shutil.which(name)
        if path:
            candidates.append(Path(path))
    env_candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    local = Path.home() / "AppData" / "Local"
    env_candidates.extend([
        local / "Google" / "Chrome" / "Application" / "chrome.exe",
        local / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/microsoft-edge"),
    ])
    candidates.extend(env_candidates)
    seen = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            return path
    return None


def export_pdf(html_path, pdf_path, browser_path):
    last_error = ""
    with tempfile.TemporaryDirectory(prefix="book-builder-", dir=pdf_path.parent) as profile_dir:
        base = [
            str(browser_path),
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--print-to-pdf-no-header",
            "--virtual-time-budget=12000",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--metrics-recording-only",
            f"--user-data-dir={profile_dir}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        commands = [
            [base[0], "--headless=new", *base[1:]],
            [base[0], "--headless", *base[1:]],
        ]
        for command in commands:
            proc = subprocess.run(command, capture_output=True, text=True)
            if proc.returncode == 0 and pdf_path.exists():
                return
            last_error = (proc.stderr or proc.stdout or "").strip()
    raise RuntimeError(f"browser failed to export pdf: {last_error}")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    chapters = discover_chapters()
    collect_headings(chapters)

    markdown_path = output_dir / f"{args.title}.md"
    html_path = output_dir / f"{args.title}.html"
    pdf_path = output_dir / f"{args.title}.pdf"

    markdown_path.write_text(build_markdown(chapters, args.title, args.toc_depth), encoding="utf-8")
    html_path.write_text(build_html(chapters, args.title, args.toc_depth), encoding="utf-8")

    print(f"[book-builder] markdown: {markdown_path}")
    print(f"[book-builder] html: {html_path}")

    if args.pdf:
        browser_path = find_browser(args.browser)
        if browser_path is None:
            raise RuntimeError(
                "cannot find a supported browser for pdf export. "
                "Please install Microsoft Edge or Google Chrome, "
                "or pass --browser with the executable path."
            )
        export_pdf(html_path, pdf_path, browser_path)
        print(f"[book-builder] pdf: {pdf_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[book-builder] error: {exc}", file=sys.stderr)
        sys.exit(1)
