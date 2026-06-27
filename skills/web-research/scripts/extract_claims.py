#!/usr/bin/env python3
"""Normalise a block of retrieved text into clean, de-duplicated bullet points.

A small, deterministic helper a Skill can run instead of spending model tokens
on mechanical reformatting (progressive disclosure, level 3). Reads text from a
file argument or stdin and prints one trimmed sentence per line.

Usage:
    python extract_claims.py [path]      # or pipe text on stdin
"""
from __future__ import annotations

import re
import sys


def extract(text: str) -> list[str]:
    # Split into sentence-ish units on ., !, ? or newlines.
    raw = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    seen: set[str] = set()
    out: list[str] = []
    for s in raw:
        s = s.strip(" \t-•*")
        if len(s) < 8:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def main() -> int:
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding="utf-8").read()
    else:
        text = sys.stdin.read()
    for line in extract(text):
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
