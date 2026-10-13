"""Deduplicate merged_dataset.csv.

By default, duplicates are identified by the entire row across all columns after
whitespace-normalizing each cell. This is the safest interpretation of
"same row inputs" while preserving the original data.

Usage:
    python dedupe_merged_dataset.py
    python dedupe_merged_dataset.py --input merged_dataset.csv --in-place
    python dedupe_merged_dataset.py --input merged_dataset.csv --output merged_dataset_dedup.csv

Advanced:
    python dedupe_merged_dataset.py --key-columns Author,Texts --in-place
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from typing import Iterable


_WHITESPACE_RE = re.compile(r"\s+")


def _norm(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def _parse_columns_arg(value: str) -> list[str]:
    parts = [p.strip() for p in (value or "").split(",")]
    return [p for p in parts if p]


def dedupe_csv(
    input_path: str,
    output_path: str,
    *,
    key_columns: list[str] | None = None,
) -> tuple[int, int]:
    """Return (rows_in, rows_out)."""
    rows_in = 0
    rows_out = 0
    seen: set[tuple[str, ...]] = set()

    with open(input_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header")

        # Preserve the original column order.
        fieldnames: list[str] = list(reader.fieldnames)

        if key_columns is None:
            key_columns = list(fieldnames)
        else:
            missing = [c for c in key_columns if c not in fieldnames]
            if missing:
                raise ValueError(f"Input CSV missing key columns: {missing}")

        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                rows_in += 1
                # If there's a Texts column, skip rows with empty text entirely.
                if "Texts" in fieldnames and not _norm(row.get("Texts", "")):
                    continue

                key = tuple(_norm(row.get(col, "")) for col in key_columns)
                if key in seen:
                    continue
                seen.add(key)

                # Keep original (non-normalized) values to avoid altering content.
                writer.writerow(row)
                rows_out += 1

    return rows_in, rows_out


def main(argv: list[str] | None = None) -> int:
    default_input = os.path.join(os.path.dirname(__file__), "merged_dataset.csv")

    parser = argparse.ArgumentParser(description="Remove duplicates from merged_dataset.csv")
    parser.add_argument("--input", default=default_input, help="Input CSV path")
    parser.add_argument(
        "--output",
        default="",
        help="Output CSV path (omit when using --in-place)",
    )
    parser.add_argument(
        "--key-columns",
        default="",
        help=(
            "Comma-separated list of columns to use as the duplicate key. "
            "Default: all columns (full-row dedupe)."
        ),
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite input file in-place (safe temp file + atomic replace)",
    )
    args = parser.parse_args(argv)

    key_columns = _parse_columns_arg(args.key_columns) if args.key_columns else None

    input_path = args.input
    if args.in_place:
        tmp_path = input_path + ".tmp"
        rows_in, rows_out = dedupe_csv(input_path, tmp_path, key_columns=key_columns)
        try:
            os.replace(tmp_path, input_path)
        except PermissionError:
            # On Windows (especially with OneDrive sync), the destination file can
            # be temporarily locked which prevents atomic replace. Fall back to a
            # copy-over rewrite.
            with open(tmp_path, "rb") as src, open(input_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(tmp_path)
        print(f"Deduped in-place: {rows_in} -> {rows_out} rows ({rows_in - rows_out} removed)")
        print(f"Output: {input_path}")
        return 0

    output_path = args.output or os.path.join(os.path.dirname(input_path), "merged_dataset_dedup.csv")
    rows_in, rows_out = dedupe_csv(input_path, output_path, key_columns=key_columns)
    print(f"Deduped: {rows_in} -> {rows_out} rows ({rows_in - rows_out} removed)")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
