from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import COURSES_DIR


def slugify(value: str) -> str:
    value = value.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:63] or "kurs"


class CourseStore:
    def __init__(self, root: Path = COURSES_DIR) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, course_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", course_id):
            raise ValueError("Ungültige Kurs-ID")
        return self.root / course_id

    def course_path(self, course_id: str) -> Path:
        return self.directory(course_id) / "course.json"

    def load(self, course_id: str) -> dict:
        path = self.course_path(course_id)
        if not path.exists():
            raise KeyError(course_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, course_id: str, payload: dict) -> None:
        directory = self.directory(course_id)
        directory.mkdir(parents=True, exist_ok=True)
        self.course_path(course_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[dict]:
        courses = []
        for path in sorted(self.root.glob("*/course.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            courses.append({key: data.get(key) for key in ("id", "name", "description", "language") } | {"chunks": len(data.get("chunks", []))})
        return courses

    def create(self, name: str, description: str, tutor_role: str, language: str) -> dict:
        base = slugify(name)
        course_id = base
        counter = 2
        while self.course_path(course_id).exists():
            course_id = f"{base[:58]}-{counter}"
            counter += 1
        payload = {"version": 3, "id": course_id, "name": name, "description": description,
                   "tutor_role": tutor_role, "language": language, "chunks": []}
        self.save(course_id, payload)
        return payload

    def invalidate_index(self, course_id: str) -> None:
        cache = self.directory(course_id) / "index"
        if cache.exists():
            shutil.rmtree(cache)

    def delete(self, course_id: str) -> None:
        directory = self.directory(course_id)
        if not self.course_path(course_id).exists():
            raise KeyError(course_id)
        shutil.rmtree(directory)

    def save_source(self, course_id: str, filename: str, content: bytes) -> str:
        source_dir = self.directory(course_id) / "sources"
        source_dir.mkdir(parents=True, exist_ok=True)
        original = Path(filename).name
        stem = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß._-]+", "-", Path(original).stem).strip("-.") or "dokument"
        suffix = Path(original).suffix.lower()
        candidate = source_dir / f"{stem}{suffix}"
        counter = 2
        while candidate.exists():
            candidate = source_dir / f"{stem}-{counter}{suffix}"
            counter += 1
        candidate.write_bytes(content)
        return candidate.name
