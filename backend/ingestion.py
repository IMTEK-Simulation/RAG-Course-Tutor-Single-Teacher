from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from pathlib import Path


ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".tex", ".pdf"}


def clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "nav", "footer", "svg"} or self.skip:
            self.skip += 1
        elif tag in {"h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            self.skip -= 1
        elif tag in {"h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote"}:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Dateityp {suffix or '(ohne Endung)'} wird nicht unterstützt")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = [f"# Seite {number}\n\n{page.extract_text() or ''}" for number, page in enumerate(reader.pages, 1)]
        return clean("\n\n".join(pages))
    raw = content.decode("utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        parser = HTMLTextParser()
        parser.feed(raw)
        return clean("".join(parser.parts))
    if suffix == ".tex":
        raw = re.sub(r"(?m)^\s*%.*$", "", raw)
        raw = re.sub(r"\\(chapter|section|subsection|subsubsection)\*?\{([^}]*)\}", r"\n\n# \2\n\n", raw)
    return clean(raw)


def split_units(text: str) -> list[tuple[str, str]]:
    heading = "Allgemein"
    units: list[tuple[str, str]] = []
    buffer: list[str] = []
    for block in re.split(r"\n{2,}", text):
        block = block.strip()
        if not block:
            continue
        match = re.match(r"^#{1,6}\s+(.+)$", block)
        if match or (len(block) < 100 and "\n" not in block and not block.endswith((".", "!", "?", ":", ";"))):
            if buffer:
                units.append((heading, "\n\n".join(buffer)))
                buffer = []
            heading = (match.group(1) if match else block).strip()
        else:
            buffer.append(block)
    if buffer:
        units.append((heading, "\n\n".join(buffer)))
    return units or [("Allgemein", text)]


def chunk_text(text: str, max_chars: int = 1600, overlap_chars: int = 160) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    for heading, unit in split_units(text):
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", unit) if p.strip()]
        current = ""
        for paragraph in paragraphs:
            pieces = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9])", paragraph) if len(paragraph) > max_chars else [paragraph]
            for piece in pieces:
                candidate = f"{current}\n\n{piece}".strip()
                if current and len(candidate) > max_chars:
                    chunks.append((heading, current))
                    tail = current[-overlap_chars:].lstrip() if overlap_chars else ""
                    current = f"{tail}\n\n{piece}".strip()
                else:
                    current = candidate
        if current:
            chunks.append((heading, current))
    return chunks


def quality_flags(text: str, section: str) -> list[str]:
    flags = []
    if len(text) < 120: flags.append("sehr_kurz")
    if len(text) > 1800: flags.append("sehr_lang")
    if text.count("\\begin{") != text.count("\\end{"): flags.append("unvollstaendige_umgebung")
    if section == "Allgemein": flags.append("keine_ueberschrift")
    if len(set(re.findall(r"\w+", text.lower()))) < 12: flags.append("wenig_inhalt")
    return flags


def build_chunks(course: dict, filename: str, content: bytes) -> list[dict]:
    text = extract_text(filename, content)
    stem = re.sub(r"[^a-z0-9]+", "-", Path(filename).stem.lower()).strip("-") or "dokument"
    existing_ids = {item["id"] for item in course.get("chunks", [])}
    output = []
    next_number = len(existing_ids) + 1
    for number, (section, part) in enumerate(chunk_text(text), 1):
        chunk_id = f"{stem}-{next_number:04d}"
        while chunk_id in existing_ids:
            next_number += 1
            chunk_id = f"{stem}-{next_number:04d}"
        existing_ids.add(chunk_id)
        next_number += 1
        output.append({
            "id": chunk_id, "course": course["name"], "module": "Import",
            "topic": section, "title": Path(filename).stem, "section": section, "language": course.get("language", "auto"),
            "content_type": "uploaded", "source_file": filename, "part": number, "quality_flags": quality_flags(part, section), "text": part,
        })
    return output
