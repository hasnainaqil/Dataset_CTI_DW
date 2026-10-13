"""Merge and normalize CTI/DW datasets into a single CSV.

Inputs (expected next to this script):
- Malay1.csv
- Malay2.csv
- MarketPlace1.csv
- MarketPlace2.csv
- MarketPlace3.csv

Output columns (exactly):
1) Author
2) Texts
3) Language
4) Threat_Confidence
5) Threat_Level
"""

from __future__ import annotations

import argparse
import csv
import codecs
import os
import re
from dataclasses import dataclass
from typing import Iterable, Iterator


OUTPUT_COLUMNS = [
	"Author",
	"Texts",
	"Language",
	"Threat_Confidence",
	"Threat_Level",
]


_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: str) -> str:
	value = (value or "").strip()
	value = _WHITESPACE_RE.sub(" ", value)
	return value


def _open_text_file(path: str):
	"""Open a CSV file with a couple common encodings."""
	# Some of these datasets include invalid UTF-8 bytes. Detect this up-front
	# (without loading the full file into memory) so csv parsing won't crash
	# mid-iteration.
	decoder = codecs.getincrementaldecoder("utf-8")("strict")
	is_utf8 = True
	with open(path, "rb") as bf:
		while True:
			chunk = bf.read(8192)
			if not chunk:
				break
			try:
				decoder.decode(chunk)
			except UnicodeDecodeError:
				is_utf8 = False
				break

	encoding = "utf-8-sig" if is_utf8 else "latin-1"
	return open(path, "r", newline="", encoding=encoding)


@dataclass(frozen=True)
class NormalizedRow:
	author: str
	texts: str

	def to_output_row(self) -> dict[str, str]:
		# Keep empties as empty strings. In CSV, empty cells are the standard
		# way to represent missing values (floats can be empty too).
		return {
			"Author": self.author,
			"Texts": self.texts,
			"Language": "",
			"Threat_Confidence": "",
			"Threat_Level": "",
		}


def _read_malay1(path: str) -> Iterator[NormalizedRow]:
	# Header: text,id,sentiment,...
	with _open_text_file(path) as f:
		reader = csv.DictReader(f)
		for row in reader:
			text = _clean_text(row.get("text", ""))
			if not text:
				continue
			yield NormalizedRow(author="", texts=text)


def _read_malay2(path: str) -> Iterator[NormalizedRow]:
	# Header: Tweet,Sentiment
	with _open_text_file(path) as f:
		reader = csv.DictReader(f)
		for row in reader:
			text = _clean_text(row.get("Tweet", ""))
			if not text:
				continue
			yield NormalizedRow(author="", texts=text)


def _read_marketplace1(path: str) -> Iterator[NormalizedRow]:
	# No header. Sample rows:
	# 10086,"Hacking for Profit: ...","junkiepig666",2.73 EUR, Germany
	with _open_text_file(path) as f:
		reader = csv.reader(f)
		for row in reader:
			if not row:
				continue
			# Defensive: tolerate weird/short rows.
			title = _clean_text(row[1]) if len(row) > 1 else ""
			author = _clean_text(row[2]) if len(row) > 2 else ""
			if not title:
				continue
			yield NormalizedRow(author=author, texts=title)


def _read_marketplace2(path: str) -> Iterator[NormalizedRow]:
	# No header. Often quoted values.
	# Sample rows:
	# "2016-...", "18365", "50gr. FUB-AKB", "ALaurizen", "USD 340.00", "Drugs", "China"
	# Sometimes appears to have 6 fields instead of 7.
	with _open_text_file(path) as f:
		reader = csv.reader(f, skipinitialspace=True)
		for row in reader:
			if not row:
				continue
			# Expected: date, id, item, vendor, price, category, origin
			item = _clean_text(row[2]) if len(row) > 2 else ""
			author = _clean_text(row[3]) if len(row) > 3 else ""
			category = _clean_text(row[5]) if len(row) > 5 else ""

			# Keep “full text” for the row by including category when present.
			parts = [p for p in [item, category] if p]
			text = _clean_text(" ".join(parts))
			if not text:
				continue
			yield NormalizedRow(author=author, texts=text)


def _read_marketplace3(path: str) -> Iterator[NormalizedRow]:
	# Header: Vendor, Category, Item, Item Description, ...
	with _open_text_file(path) as f:
		reader = csv.DictReader(f, skipinitialspace=True)
		for row in reader:
			author = _clean_text(row.get("Vendor", ""))
			item = _clean_text(row.get("Item", ""))
			desc = _clean_text(row.get("Item Description", ""))
			category = _clean_text(row.get("Category", ""))

			parts = [p for p in [item, desc, category] if p]
			text = _clean_text(" ".join(parts))
			if not text:
				continue
			yield NormalizedRow(author=author, texts=text)


def _iter_all_rows(dataset_dir: str) -> Iterator[NormalizedRow]:
	inputs = [
		("Malay1.csv", _read_malay1),
		("Malay2.csv", _read_malay2),
		("MarketPlace1.csv", _read_marketplace1),
		("MarketPlace2.csv", _read_marketplace2),
		("MarketPlace3.csv", _read_marketplace3),
	]

	for filename, reader_fn in inputs:
		path = os.path.join(dataset_dir, filename)
		if not os.path.exists(path):
			raise FileNotFoundError(f"Missing input file: {path}")
		yield from reader_fn(path)


def write_merged_csv(output_path: str, rows: Iterable[NormalizedRow]) -> int:
	os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
	count = 0
	with open(output_path, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
		writer.writeheader()
		for row in rows:
			writer.writerow(row.to_output_row())
			count += 1
	return count


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="Merge Malay + MarketPlace CSVs into a normalized 5-column CSV."
	)
	parser.add_argument(
		"--input-dir",
		default=os.path.dirname(__file__),
		help="Directory containing the 5 source CSV files (default: script directory).",
	)
	parser.add_argument(
		"-o",
		"--output",
		default=os.path.join(os.path.dirname(__file__), "merged_dataset.csv"),
		help="Output CSV path (default: merged_dataset.csv in the script directory).",
	)
	args = parser.parse_args(argv)

	rows = list(_iter_all_rows(args.input_dir))
	written = write_merged_csv(args.output, rows)
	print(f"Wrote {written} rows to: {args.output}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

