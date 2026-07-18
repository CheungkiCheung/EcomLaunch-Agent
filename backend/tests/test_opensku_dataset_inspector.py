from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.opensku_data.inspect_dataset_sample import (  # noqa: E402
    infer_schema,
    write_jsonl_sample,
)


def test_infer_schema_summarizes_fields_across_rows():
    rows = [
        {"order_id": "o-1", "price": "19.90", "tags": ["launch"], "extra": None},
        {"order_id": "o-2", "price": "21", "tags": [], "review_score": 5},
    ]

    schema = infer_schema("olist", "orders", rows, "https://example.test/orders.csv")

    assert schema["dataset"] == "olist"
    assert schema["component"] == "orders"
    assert schema["source_url"] == "https://example.test/orders.csv"
    assert schema["row_count"] == 2
    assert schema["fields"]["order_id"]["observed_types"] == ["string"]
    assert schema["fields"]["price"]["observed_types"] == ["number_string"]
    assert schema["fields"]["tags"]["observed_types"] == ["array"]
    assert schema["fields"]["review_score"]["observed_types"] == ["integer"]
    assert schema["fields"]["extra"]["observed_types"] == ["null"]


def test_write_jsonl_sample_preserves_dataset_component_and_rows(tmp_path):
    rows = [{"query": "smart coffee table"}, {"query": "salon chair"}]
    output_path = tmp_path / "sample.jsonl"

    write_jsonl_sample(output_path, "wands", "query", rows)

    written = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert written == [
        {"dataset": "wands", "component": "query", "row": {"query": "smart coffee table"}},
        {"dataset": "wands", "component": "query", "row": {"query": "salon chair"}},
    ]

