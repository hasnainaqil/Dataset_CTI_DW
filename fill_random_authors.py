"""Fill empty Author cells with random existing author names.

Reads a CSV with an `Author` column, collects existing non-empty authors, then
rewrites the CSV (in-place by default) replacing empty Author values with a
randomly selected existing author.

Randomness uses `secrets.choice` for strong randomness.

Usage:
  python fill_random_authors.py --in-place
  python fill_random_authors.py --input merged_dataset.csv --output merged_dataset_authors_filled.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import secrets
import re


_WHITESPACE_RE = re.compile(r"\s+")


def _norm(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def collect_authors(input_path: str) -> list[str]:
    authors: list[str] = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header")
        if "Author" not in reader.fieldnames:
            raise ValueError("Input CSV missing 'Author' column")

        for row in reader:
            author = _norm(row.get("Author", ""))
            if author:
                authors.append(author)

    # If there are very few authors, randomness won't be great, but this meets
    # the requirement of sampling from existing names.
    return authors


def fill_empty_authors(input_path: str, output_path: str, authors: list[str]) -> tuple[int, int]:
    """Return (rows_in, filled_count)."""
    if not authors:
        raise ValueError("No non-empty authors found; cannot fill empty Author cells")

    rows_in = 0
    filled = 0

    with open(input_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "Author" not in fieldnames:
            raise ValueError("Input CSV missing 'Author' column")

        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                rows_in += 1
                current = _norm(row.get("Author", ""))
                if not current:
                    row["Author"] = secrets.choice(authors)
                    filled += 1
                writer.writerow(row)

    return rows_in, filled


def main(argv: list[str] | None = None) -> int:
    default_input = os.path.join(os.path.dirname(__file__), "merged_dataset.csv")

    parser = argparse.ArgumentParser(description="Fill empty Author cells with random existing names")
    parser.add_argument("--input", default=default_input, help="Input CSV path")
    parser.add_argument("--output", default="", help="Output CSV path")
    parser.add_argument("--in-place", action="store_true", help="Rewrite the input file in-place")
    args = parser.parse_args(argv)

    input_path = args.input
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    authors = collect_authors(input_path)

    if args.in_place:
        tmp_path = input_path + ".tmp"
        rows_in, filled = fill_empty_authors(input_path, tmp_path, authors)
        os.replace(tmp_path, input_path)
        print(f"Filled {filled} empty Author cells out of {rows_in} rows")
        print(f"Output: {input_path}")
        return 0

    output_path = args.output or os.path.join(os.path.dirname(input_path), "merged_dataset_authors_filled.csv")
    rows_in, filled = fill_empty_authors(input_path, output_path, authors)
    print(f"Filled {filled} empty Author cells out of {rows_in} rows")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
