import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.data_inspector.tools import (
    DataInspectorError,
    analyze_ab_test_tool,
    analyze_binary_ab_test,
    inspect_data_tool,
    inspect_uploads,
    query_data_tool,
    query_uploads,
)


def _runtime(uploads_dir: Path):
    return SimpleNamespace(
        state={"thread_data": {"uploads_path": str(uploads_dir)}},
        context={"thread_id": "data-inspector-test"},
        config={"configurable": {"thread_id": "data-inspector-test"}},
    )


def test_inspect_csv_returns_alias_schema_quality_and_time_range(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "订单数据.csv").write_text(
        "订单号,支付时间,商品,实付金额\nA-1,2026-07-01 10:00:00,咖啡杯,99.00\nA-2,2026-07-02 11:30:00,滤纸,29.00\nA-2,2026-07-02 11:30:00,滤纸,29.00\n",
        encoding="utf-8",
    )

    result = inspect_uploads(uploads)

    assert result["ok"] is True
    assert result["table_count"] == 1
    table = result["tables"][0]
    assert table["alias"] == "table_1"
    assert table["filename"] == "订单数据.csv"
    assert table["row_count"] == 3
    assert table["duplicate_row_count"] == 1
    columns = {column["name"]: column for column in table["columns"]}
    assert columns["订单号"]["unique_count"] == 2
    assert columns["实付金额"]["numeric"]["max"] == 99.0
    assert columns["支付时间"]["datetime"]["min"] == "2026-07-01T10:00:00"
    assert columns["支付时间"]["datetime"]["max"] == "2026-07-02T11:30:00"
    assert "query_data" in result["sql_guidance"]


def test_inspect_xlsx_reads_each_sheet(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    workbook = uploads / "store.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"order_id": ["A", "B"], "amount": [10, 20]}).to_excel(writer, sheet_name="Orders", index=False)
        pd.DataFrame({"content_id": ["N1"], "views": [100]}).to_excel(writer, sheet_name="Content", index=False)

    result = inspect_uploads(uploads)

    assert result["table_count"] == 2
    assert {(table["alias"], table["sheet"]) for table in result["tables"]} == {
        ("store_orders", "Orders"),
        ("store_content", "Content"),
    }


def test_query_uploads_computes_content_rate_from_chinese_columns(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "xiaohongshu.csv").write_text(
        "笔记ID,曝光量,收藏量\nN1,1000,60\nN2,500,15\n",
        encoding="utf-8",
    )

    result = query_uploads(
        uploads,
        'SELECT SUM("收藏量")::DOUBLE / NULLIF(SUM("曝光量"), 0) AS save_rate FROM xiaohongshu',
    )

    assert result["ok"] is True
    assert result["columns"] == ["save_rate"]
    assert result["rows"][0]["save_rate"] == pytest.approx(0.05)


def test_query_uploads_coerces_high_confidence_date_columns(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text(
        "order_id,payment_time,amount\nO1,2026-07-01 10:00:00,10\nO2,2026-07-02 11:00:00,20\n",
        encoding="utf-8",
    )

    result = query_uploads(
        uploads,
        "SELECT MIN(payment_time) AS first_payment, MAX(payment_time) AS last_payment FROM orders",
    )

    assert result["rows"] == [
        {
            "first_payment": "2026-07-01T10:00:00",
            "last_payment": "2026-07-02T11:00:00",
        }
    ]


def test_query_uploads_supports_multi_file_join(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text("order_id,product_id,amount\nO1,P1,30\nO2,P2,50\n", encoding="utf-8")
    (uploads / "products.csv").write_text("product_id,product_name\nP1,杯子\nP2,滤纸\n", encoding="utf-8")

    result = query_uploads(
        uploads,
        "SELECT p.product_name, SUM(o.amount) AS revenue FROM orders o JOIN products p USING (product_id) GROUP BY p.product_name ORDER BY revenue DESC",
    )

    assert result["rows"] == [
        {"product_name": "滤纸", "revenue": 50.0},
        {"product_name": "杯子", "revenue": 30.0},
    ]


def test_query_allows_joined_row_counts(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text("order_id\nO1\nO2\n", encoding="utf-8")
    (uploads / "items.csv").write_text("order_id,item_id\nO1,I1\nO1,I2\nO2,I3\n", encoding="utf-8")

    result = query_uploads(uploads, "SELECT COUNT(*) AS rows FROM orders JOIN items USING (order_id)")

    assert result["rows"] == [{"rows": 3}]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * FROM read_csv_auto('/etc/passwd')",
        "SELECT 1; SELECT 2",
        "SELECT 1 -- comment",
        "ATTACH '/tmp/other.db' AS other",
    ],
)
def test_query_uploads_rejects_non_read_only_or_external_sql(tmp_path: Path, sql: str) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text("order_id,amount\nO1,30\n", encoding="utf-8")

    with pytest.raises(DataInspectorError):
        query_uploads(uploads, sql)


def test_inspect_rejects_upload_path_traversal(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("secret\nvalue\n", encoding="utf-8")

    with pytest.raises(DataInspectorError, match="上传目录之外"):
        inspect_uploads(uploads, ["../outside.csv"])


def test_query_truncates_results_to_requested_limit(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "numbers.csv").write_text("value\n1\n2\n3\n", encoding="utf-8")

    result = query_uploads(uploads, "SELECT value FROM numbers ORDER BY value", max_rows=2)

    assert result["truncated"] is True
    assert result["row_count"] == 2
    assert result["rows"] == [{"value": 1}, {"value": 2}]


@pytest.mark.parametrize("delimiter", ["\t", ";", "|"])
def test_inspect_csv_supports_common_export_delimiters(tmp_path: Path, delimiter: str) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "export.csv").write_text(f"content_id{delimiter}views\nN1{delimiter}100\n", encoding="utf-8")

    result = inspect_uploads(uploads)

    table = result["tables"][0]
    assert [column["name"] for column in table["columns"]] == ["content_id", "views"]
    assert table["sample_rows"] == [{"content_id": "N1", "views": 100}]


def test_inspect_hides_free_text_samples_by_default_and_bounds_opt_in_text(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    long_text = "很长的评论" * 100
    (uploads / "reviews.csv").write_text(f"review_id,comment\nR1,{long_text}\n", encoding="utf-8")

    result = inspect_uploads(uploads, sample_rows=1)

    table = result["tables"][0]
    assert all("samples" not in column for column in table["columns"])
    assert table["sample_rows"][0]["comment"] == "[text omitted]"

    text_result = inspect_uploads(uploads, sample_rows=1, include_text_samples=True)
    text_sample = text_result["tables"][0]["sample_rows"][0]["comment"]
    assert text_sample.endswith("...")
    assert len(text_sample) == 160


def test_inspect_rejects_excessive_sample_rows(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "orders.csv").write_text("order_id\nO1\n", encoding="utf-8")

    with pytest.raises(DataInspectorError, match="1 到 3"):
        inspect_uploads(uploads, sample_rows=4)


def test_tools_return_user_correctable_errors_as_json(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    runtime = _runtime(uploads)

    inspect_result = json.loads(inspect_data_tool.func(runtime=runtime))
    query_result = json.loads(query_data_tool.func(runtime=runtime, sql="SELECT 1"))

    assert inspect_result["ok"] is False
    assert "CSV 或 XLSX" in inspect_result["error"]
    assert query_result["ok"] is False
    assert "CSV 或 XLSX" in query_result["error"]


def test_analyze_binary_ab_test_returns_significance_interval_and_srm() -> None:
    result = analyze_binary_ab_test(
        control_visitors=10_000,
        control_conversions=1_200,
        variant_visitors=10_000,
        variant_conversions=1_320,
    )

    assert result["ok"] is True
    assert result["control_rate"] == pytest.approx(0.12)
    assert result["variant_rate"] == pytest.approx(0.132)
    assert result["absolute_difference"] == pytest.approx(0.012)
    assert result["relative_lift"] == pytest.approx(0.1)
    assert result["p_value"] == pytest.approx(0.010558899038851665)
    assert result["p_value"] < 0.05
    assert result["significant"] is True
    assert result["confidence_interval"]["lower"] > 0
    assert result["confidence_interval"]["upper"] > result["confidence_interval"]["lower"]
    assert result["sample_ratio_mismatch_detected"] is False
    assert result["sample_ratio_mismatch_p_value"] == pytest.approx(1.0)


def test_analyze_binary_ab_test_handles_zero_control_rate_without_division() -> None:
    result = analyze_binary_ab_test(
        control_visitors=500,
        control_conversions=0,
        variant_visitors=500,
        variant_conversions=0,
    )

    assert result["relative_lift"] is None
    assert result["z_score"] == 0
    assert result["p_value"] == 1
    assert result["significant"] is False


def test_analyze_binary_ab_test_detects_sample_ratio_mismatch() -> None:
    result = analyze_binary_ab_test(
        control_visitors=800,
        control_conversions=80,
        variant_visitors=200,
        variant_conversions=20,
        expected_control_share=0.5,
    )

    assert result["observed_control_share"] == pytest.approx(0.8)
    assert result["sample_ratio_mismatch_p_value"] < 0.001
    assert result["sample_ratio_mismatch_detected"] is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"control_visitors": 0}, "必须大于 0"),
        ({"control_conversions": 101}, "不能大于"),
        ({"variant_conversions": -1}, "不能为负数"),
        ({"confidence_level": 1.0}, "小于 1.0"),
        ({"expected_control_share": 0.0}, "大于 0"),
    ],
)
def test_analyze_binary_ab_test_rejects_invalid_inputs(overrides: dict[str, int | float], message: str) -> None:
    inputs: dict[str, int | float] = {
        "control_visitors": 100,
        "control_conversions": 10,
        "variant_visitors": 100,
        "variant_conversions": 12,
    }
    inputs.update(overrides)

    with pytest.raises(DataInspectorError, match=message):
        analyze_binary_ab_test(**inputs)


def test_analyze_ab_test_tool_returns_user_correctable_errors_as_json() -> None:
    result = json.loads(
        analyze_ab_test_tool.func(
            control_visitors=100,
            control_conversions=101,
            variant_visitors=100,
            variant_conversions=10,
        )
    )

    assert result["ok"] is False
    assert "不能大于" in result["error"]
