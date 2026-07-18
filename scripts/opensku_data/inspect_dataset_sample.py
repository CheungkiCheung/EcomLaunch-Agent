#!/usr/bin/env python3
"""Inspect small public dataset samples for OpenSKU.

The script intentionally uses only Python's standard library so Phase 1 data
validation can run from the repository root with:

    uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset olist --limit 5
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUEST_TIMEOUT_SECONDS = 45
RANGE_SAMPLE_BYTES = 2 * 1024 * 1024
USER_AGENT = "OpenSKU dataset inspector/0.1"
SSL_CONTEXT = None


@dataclass(frozen=True)
class DatasetComponent:
    name: str
    url: str
    format: str
    note: str


DATASETS: dict[str, list[DatasetComponent]] = {
    "olist": [
        DatasetComponent(
            "orders",
            "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_orders_dataset.csv",
            "csv",
            "Order lifecycle timestamps and delivery status.",
        ),
        DatasetComponent(
            "order_items",
            "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_items_dataset.csv",
            "csv",
            "Order-item price, freight, seller, and product linkage.",
        ),
        DatasetComponent(
            "order_reviews",
            "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_reviews_dataset.csv",
            "csv",
            "Post-purchase review scores and review text.",
        ),
        DatasetComponent(
            "order_payments",
            "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_order_payments_dataset.csv",
            "csv",
            "Payment type, installments, and payment value.",
        ),
        DatasetComponent(
            "products",
            "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/olist_products_dataset.csv",
            "csv",
            "Product category, dimensions, and photo/text metadata counts.",
        ),
    ],
    "amazon_reviews": [
        DatasetComponent(
            "all_beauty_reviews",
            "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/All_Beauty.jsonl.gz",
            "jsonl.gz",
            "Review ratings, review text, timestamps, helpful votes, and verified-purchase flags.",
        ),
        DatasetComponent(
            "all_beauty_metadata",
            "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_All_Beauty.jsonl.gz",
            "jsonl.gz",
            "Item metadata for matching reviews to product titles, descriptions, price, images, and store context.",
        ),
    ],
    "wands": [
        DatasetComponent(
            "query",
            "https://raw.githubusercontent.com/wayfair/WANDS/main/dataset/query.csv",
            "csv",
            "Search queries and query classes.",
        ),
        DatasetComponent(
            "product",
            "https://raw.githubusercontent.com/wayfair/WANDS/main/dataset/product.csv",
            "csv",
            "Candidate products, descriptions, feature strings, ratings, and review counts.",
        ),
        DatasetComponent(
            "label",
            "https://raw.githubusercontent.com/wayfair/WANDS/main/dataset/label.csv",
            "csv",
            "Query-product relevance labels.",
        ),
    ],
}


TYPE_ORDER = {
    "null": 0,
    "boolean": 1,
    "integer": 2,
    "float": 3,
    "number_string": 4,
    "empty_string": 5,
    "string": 6,
    "array": 7,
    "object": 8,
}

NUMBER_STRING_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")


def detect_scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return "empty_string"
        if NUMBER_STRING_RE.match(stripped):
            return "number_string"
        return "string"
    return type(value).__name__


def infer_schema(
    dataset: str,
    component: str,
    rows: list[dict[str, Any]],
    source_url: str,
) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key, value in row.items():
            entry = fields.setdefault(
                key,
                {
                    "observed_types": set(),
                    "non_null_count": 0,
                    "example_values": [],
                },
            )
            value_type = detect_scalar_type(value)
            entry["observed_types"].add(value_type)
            if value is not None and value != "":
                entry["non_null_count"] += 1
                if len(entry["example_values"]) < 3:
                    entry["example_values"].append(shorten_value(value))

    normalized_fields = {}
    for key in sorted(fields):
        entry = fields[key]
        observed_types = sorted(
            entry["observed_types"],
            key=lambda item: TYPE_ORDER.get(item, 99),
        )
        normalized_fields[key] = {
            "observed_types": observed_types,
            "non_null_count": entry["non_null_count"],
            "example_values": entry["example_values"],
        }

    return {
        "dataset": dataset,
        "component": component,
        "source_url": source_url,
        "row_count": len(rows),
        "fields": normalized_fields,
    }


def shorten_value(value: Any, max_length: int = 160) -> Any:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    if len(text) <= max_length:
        return value
    return text[: max_length - 1] + "..."


def write_jsonl_sample(
    output_path: Path,
    dataset: str,
    component: str,
    rows: list[dict[str, Any]],
    mode: str = "w",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "dataset": dataset,
                        "component": component,
                        "row": row,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def inspect_dataset(dataset: str, limit: int, output_root: Path) -> dict[str, Any]:
    if dataset not in DATASETS:
        available = ", ".join(sorted(DATASETS))
        raise ValueError(f"Unknown dataset '{dataset}'. Available datasets: {available}")
    if limit <= 0:
        raise ValueError("--limit must be greater than 0")

    sample_path = output_root / "samples" / f"{dataset}.jsonl"
    schema_path = output_root / "schemas" / f"{dataset}.schema.json"
    components_output: list[dict[str, Any]] = []

    for index, component in enumerate(DATASETS[dataset]):
        rows = fetch_rows(component, limit)
        if len(rows) < limit:
            raise RuntimeError(
                f"{dataset}/{component.name} returned only {len(rows)} rows; expected {limit}"
            )

        write_jsonl_sample(
            sample_path,
            dataset,
            component.name,
            rows,
            mode="w" if index == 0 else "a",
        )
        component_schema = infer_schema(dataset, component.name, rows, component.url)
        component_schema["note"] = component.note
        component_schema["format"] = component.format
        components_output.append(component_schema)

    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema = {
        "dataset": dataset,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "limit_per_component": limit,
        "sample_path": str(sample_path),
        "schema_path": str(schema_path),
        "components": components_output,
    }
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return schema


def fetch_rows(component: DatasetComponent, limit: int) -> list[dict[str, Any]]:
    if component.format == "csv":
        return fetch_csv_rows(component.url, limit)
    if component.format == "jsonl.gz":
        return fetch_gzip_jsonl_rows(component.url, limit)
    raise ValueError(f"Unsupported component format: {component.format}")


def open_url(url: str, *, headers: dict[str, str] | None = None):
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    return urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
        context=get_ssl_context(),
    )


def get_ssl_context() -> ssl.SSLContext:
    global SSL_CONTEXT
    if SSL_CONTEXT is not None:
        return SSL_CONTEXT

    cafile = None
    try:
        import certifi  # type: ignore[import-not-found]

        certifi_cafile = Path(certifi.where())
        if certifi_cafile.exists():
            cafile = str(certifi_cafile)
    except Exception:
        cafile = None

    if cafile is None:
        fallback = Path("/etc/ssl/cert.pem")
        if fallback.exists():
            cafile = str(fallback)

    SSL_CONTEXT = ssl.create_default_context(cafile=cafile)
    return SSL_CONTEXT


def fetch_csv_rows(url: str, limit: int) -> list[dict[str, Any]]:
    with open_url(url) as response:
        text_stream = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        header_line = text_stream.readline()
        if not header_line:
            return []
        delimiter = detect_delimiter(header_line)
        fieldnames = next(csv.reader([header_line], delimiter=delimiter))
        reader = csv.DictReader(text_stream, fieldnames=fieldnames, delimiter=delimiter)
        rows = []
        for row in reader:
            normalized = {key: value for key, value in row.items() if key is not None}
            rows.append(normalized)
            if len(rows) >= limit:
                break
        return rows


def detect_delimiter(header_line: str) -> str:
    if header_line.count("\t") > header_line.count(","):
        return "\t"
    return ","


def fetch_gzip_jsonl_rows(url: str, limit: int) -> list[dict[str, Any]]:
    headers = {"Range": f"bytes=0-{RANGE_SAMPLE_BYTES - 1}"}
    rows: list[dict[str, Any]] = []
    try:
        response = open_url(url, headers=headers)
        try:
            gzip_stream = gzip.GzipFile(fileobj=response)
            text_stream = io.TextIOWrapper(gzip_stream, encoding="utf-8")
            for line in text_stream:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(json.loads(stripped))
                if len(rows) >= limit:
                    break
        finally:
            response.close()
    except EOFError:
        if not rows:
            raise
    return rows


def print_summary(schema: dict[str, Any]) -> None:
    print(f"dataset={schema['dataset']}")
    print(f"sample_path={schema['sample_path']}")
    print(f"schema_path={schema['schema_path']}")
    for component in schema["components"]:
        fields = ", ".join(component["fields"].keys())
        print(
            f"component={component['component']} rows={component['row_count']} "
            f"format={component['format']} fields={fields}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load a real public dataset sample and write OpenSKU sample/schema files."
    )
    parser.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/opensku"),
        help="Directory that will contain samples/ and schemas/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        schema = inspect_dataset(args.dataset, args.limit, args.output_root)
    except (OSError, urllib.error.URLError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print_summary(schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
