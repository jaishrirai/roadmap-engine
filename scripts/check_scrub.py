"""Pre-publish checks for the repo. Exit code 1 if anything is found.

1. Private blocklist: no real organisation, brand, system or person name may appear in any
   file, including inside .xlsx files. The blocklist is NOT part of the repo. Keep it in a
   folder next to the repo and point to it with --blocklist or ROADMAP_BLOCKLIST
   (default: ../roadmap-engine_private/blocklist.txt, one term per line).
2. House style: no em dashes or en dashes, and the word "production" is not used, because
   this project is described as a prototype on synthetic data.

    python scripts/check_scrub.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "venv", ".venv", "output", ".private"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".cfg", ".json", ".csv", ".gitignore", ""}
STYLE_EXEMPT = {"LICENSE", "check_scrub.py"}  # license text is verbatim; this script names the banned words
DASHES = (chr(0x2014), chr(0x2013))  # em dash, en dash (written as codes so this file stays clean)


def files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS):
            yield path


def text_of(path: Path):
    if path.suffix.lower() in {".xlsx", ".docx", ".pptx"}:
        try:
            with zipfile.ZipFile(path) as z:
                return "\n".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
        except zipfile.BadZipFile:
            return ""
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""  # images and other binaries: only their file names are checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--blocklist", default=os.environ.get("ROADMAP_BLOCKLIST", str(ROOT.parent / "roadmap-engine_private" / "blocklist.txt")))
    args = ap.parse_args()

    problems = []
    terms = []
    blocklist = Path(args.blocklist)
    if blocklist.exists():
        terms = [t.strip() for t in blocklist.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    else:
        print(f"WARNING: blocklist not found at {blocklist}; name check skipped", file=sys.stderr)
    patterns = [(t, re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.I)) for t in terms]

    for path in files():
        rel = path.relative_to(ROOT)
        text = text_of(path)
        for term, pat in patterns:
            if pat.search(text) or pat.search(str(rel)):
                problems.append(f"{rel}: contains blocked term {term!r}")
        if path.name not in STYLE_EXEMPT and path.suffix.lower() not in {".xlsx", ".docx", ".pptx"}:
            if any(d in text for d in DASHES):
                problems.append(f"{rel}: contains an em dash or en dash")
            if re.search(r"\bproduction\b", text, re.I):
                problems.append(f"{rel}: uses the word 'production' (describe it as a prototype)")

    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s) found, {len(terms)} blocked terms checked")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
