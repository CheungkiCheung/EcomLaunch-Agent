from pathlib import Path

import pandas as pd
import pytest

from app.store_operator.tools import StoreDataError, inspect_uploads, query_uploads


def _write_orders(path: Path) -> None:
    pd.DataFrame(
        [
            {"订单编号": "A-1", "下单时间": "2026-07-01", "商品": "水杯", "实付金额": 100, "退款状态": "否"},
            {"订单编号": "A-2", "下单时间": "2026-07-02", "商品": "水杯", "实付金额": 80, "退款状态": "是"},
            {"订单编号": "A-3", "下单时间": "2026-07-08", "商品": "背包", "实付金额": 60, "退款状态": "否"},
        ]
    ).to_csv(path, index=False)


def test_inspect_uploads_returns_alias_schema_and_semantic_roles(tmp_path: Path) -> None:
    _write_orders(tmp_path / "orders.csv")

    result = inspect_uploads(tmp_path)

    assert result["ok"] is True
    assert result["table_count"] == 1
    table = result["tables"][0]
    assert table["alias"] == "orders"
    assert table["row_count"] == 3
    assert table["semantic_roles"]["order_id"] == ["订单编号"]
    assert table["semantic_roles"]["time"] == ["下单时间"]
    assert table["semantic_roles"]["amount"] == ["实付金额"]


def test_inspect_uploads_reads_each_xlsx_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "店铺数据.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame([{"订单号": "1", "金额": 20}]).to_excel(writer, sheet_name="订单", index=False)
        pd.DataFrame([{"商品": "水杯", "库存": 8}]).to_excel(writer, sheet_name="库存", index=False)

    result = inspect_uploads(tmp_path)

    assert result["table_count"] == 2
    assert {table["sheet"] for table in result["tables"]} == {"订单", "库存"}
    assert len({table["alias"] for table in result["tables"]}) == 2


def test_query_uploads_executes_bounded_read_only_sql(tmp_path: Path) -> None:
    _write_orders(tmp_path / "orders.csv")

    result = query_uploads(
        tmp_path,
        'SELECT "商品", SUM("实付金额") AS revenue FROM orders GROUP BY "商品" ORDER BY revenue DESC',
    )

    assert result["ok"] is True
    assert result["rows"] == [
        {"商品": "水杯", "revenue": 180.0},
        {"商品": "背包", "revenue": 60.0},
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * FROM read_csv_auto('/tmp/secret.csv')",
        "SELECT * FROM orders; SELECT 1",
        "SELECT * FROM orders -- bypass",
    ],
)
def test_query_uploads_rejects_unsafe_sql(tmp_path: Path, sql: str) -> None:
    _write_orders(tmp_path / "orders.csv")

    with pytest.raises(StoreDataError):
        query_uploads(tmp_path, sql)


def test_inspect_uploads_requires_supported_file(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not tabular", encoding="utf-8")

    with pytest.raises(StoreDataError, match="CSV 或 XLSX"):
        inspect_uploads(tmp_path)
