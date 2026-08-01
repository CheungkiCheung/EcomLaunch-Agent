"""Deterministic read-only tools for uploaded store data.

The Store Operator deliberately keeps the data layer small.  The agent first
inspects CSV/XLSX uploads, then asks DuckDB to execute bounded read-only SQL
against in-memory tables.  No model is trusted to calculate business metrics
from raw rows in its context window.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from langchain.tools import tool

from deerflow.tools.types import Runtime

SUPPORTED_SUFFIXES = {".csv", ".xlsx"}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TABLE_ROWS = 300_000
MAX_COLUMNS = 120
MAX_RESULT_ROWS = 200

_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]+")
_SQL_START_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN_SQL_RE = re.compile(
    r"\b(attach|copy|install|load|pragma|create|update|insert|delete|drop|alter|"
    r"export|import|call|set|read_csv|read_csv_auto|read_parquet|read_json|"
    r"sqlite_scan|postgres_scan|httpfs)\b",
    re.IGNORECASE,
)

_SEMANTIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "order_id": ("order_id", "orderid", "订单号", "订单编号", "交易编号"),
    "time": ("date", "time", "created_at", "paid_at", "日期", "时间", "下单时间", "支付时间"),
    "amount": ("amount", "revenue", "gmv", "sales", "price", "实付", "金额", "销售额", "成交额", "收入"),
    "quantity": ("quantity", "qty", "units", "件数", "数量", "销量"),
    "product": ("product", "sku", "item", "商品", "产品", "货号"),
    "status": ("status", "state", "状态"),
    "refund": ("refund", "return", "退款", "退货", "售后"),
    "traffic": ("impression", "exposure", "click", "view", "曝光", "点击", "浏览"),
    "marketing_cost": ("ad_spend", "cost", "cpc", "广告消耗", "广告花费", "投放费用"),
    "inventory": ("inventory", "stock", "库存"),
    "profit": ("profit", "margin", "利润", "毛利"),
    "region": ("region", "province", "city", "地区", "省份", "城市"),
    "customer": ("customer", "buyer", "user_id", "客户", "买家", "用户"),
}


class StoreDataError(ValueError):
    """User-correctable uploaded-data error."""


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, Path):
        return value.name
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, separators=(",", ":"))


def _safe_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return _json_default(value) if not isinstance(value, (str, int, float, bool)) else value


def _safe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _safe_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _uploads_dir(runtime: Runtime) -> Path:
    state = runtime.state or {}
    thread_data = state.get("thread_data") or {}
    raw_path = thread_data.get("uploads_path")
    if not raw_path:
        raise StoreDataError("当前对话还没有可访问的上传目录。请先上传 CSV 或 XLSX 文件。")
    path = Path(raw_path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _supported_files(uploads_dir: Path, filenames: list[str] | None) -> list[Path]:
    requested = filenames or [path.name for path in sorted(uploads_dir.iterdir()) if path.is_file()]
    files: list[Path] = []
    seen: set[str] = set()
    for raw_name in requested:
        name = Path(raw_name).name
        if name != raw_name and not raw_name.startswith("/mnt/user-data/uploads/"):
            raise StoreDataError(f"不允许读取上传目录之外的路径：{raw_name}")
        candidate = (uploads_dir / name).resolve()
        try:
            candidate.relative_to(uploads_dir)
        except ValueError as exc:
            raise StoreDataError(f"不允许读取上传目录之外的路径：{raw_name}") from exc
        if candidate.name in seen:
            continue
        if not candidate.is_file():
            raise StoreDataError(f"未找到上传文件：{candidate.name}")
        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if candidate.stat().st_size > MAX_FILE_BYTES:
            raise StoreDataError(f"文件 {candidate.name} 超过 50 MB，第一版暂不支持。")
        seen.add(candidate.name)
        files.append(candidate)
    if not files:
        raise StoreDataError("没有找到可分析的 CSV 或 XLSX 文件。请先上传店铺数据。")
    return files


def _identifier(value: str, fallback: str) -> str:
    normalized = _IDENTIFIER_RE.sub("_", value.strip()).strip("_").lower()
    if not normalized or normalized[0].isdigit():
        return fallback
    return normalized[:64]


def _unique_alias(base: str, used: set[str]) -> str:
    alias = base
    suffix = 2
    while alias in used:
        alias = f"{base}_{suffix}"
        suffix += 1
    used.add(alias)
    return alias


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding, sep=None, engine="python", nrows=MAX_TABLE_ROWS + 1)
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.ParserError:
            try:
                return pd.read_csv(path, encoding=encoding, nrows=MAX_TABLE_ROWS + 1)
            except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                last_error = exc
    raise StoreDataError(f"无法读取 CSV 文件 {path.name}：{last_error}")


def _load_tables(uploads_dir: Path, filenames: list[str] | None = None) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    tables: dict[str, pd.DataFrame] = {}
    sources: list[dict[str, Any]] = []
    aliases: set[str] = set()
    for file_index, path in enumerate(_supported_files(uploads_dir, filenames), start=1):
        if path.suffix.lower() == ".csv":
            frame = _read_csv(path)
            alias = _unique_alias(_identifier(path.stem, f"table_{file_index}"), aliases)
            sources.append({"alias": alias, "filename": path.name, "sheet": None})
            tables[alias] = frame
            continue

        try:
            workbook = pd.ExcelFile(path)
        except Exception as exc:  # pandas/openpyxl provide several format-specific errors
            raise StoreDataError(f"无法读取 Excel 文件 {path.name}：{exc}") from exc
        for sheet_index, sheet_name in enumerate(workbook.sheet_names, start=1):
            try:
                frame = pd.read_excel(workbook, sheet_name=sheet_name, nrows=MAX_TABLE_ROWS + 1)
            except Exception as exc:
                raise StoreDataError(f"无法读取 {path.name} 的工作表 {sheet_name}：{exc}") from exc
            base = _identifier(f"{path.stem}_{sheet_name}", f"table_{file_index}_{sheet_index}")
            alias = _unique_alias(base, aliases)
            sources.append({"alias": alias, "filename": path.name, "sheet": sheet_name})
            tables[alias] = frame

    for alias, frame in tables.items():
        if len(frame.columns) > MAX_COLUMNS:
            raise StoreDataError(f"数据表 {alias} 有 {len(frame.columns)} 列，超过第一版 120 列限制。")
        if len(frame) > MAX_TABLE_ROWS:
            raise StoreDataError(f"数据表 {alias} 超过第一版 30 万行限制，请先拆分或抽样。")
        frame.columns = [str(column).strip() or f"column_{index + 1}" for index, column in enumerate(frame.columns)]
    return tables, sources


def _semantic_roles(columns: Iterable[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for column in columns:
        normalized = column.lower().replace(" ", "_")
        for role, keywords in _SEMANTIC_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                result.setdefault(role, []).append(column)
    return result


def _datetime_summary(series: pd.Series, column_name: str) -> dict[str, Any] | None:
    normalized_name = column_name.lower()
    looks_temporal = any(keyword in normalized_name for keyword in _SEMANTIC_KEYWORDS["time"])
    if not looks_temporal and not pd.api.types.is_datetime64_any_dtype(series):
        return None
    converted = pd.to_datetime(series, errors="coerce")
    non_null = int(series.notna().sum())
    parsed = int(converted.notna().sum())
    if non_null == 0 or parsed / non_null < 0.6:
        return None
    return {
        "parsed_ratio": round(parsed / non_null, 4),
        "min": _safe_scalar(converted.min()),
        "max": _safe_scalar(converted.max()),
    }


def _column_profile(series: pd.Series, name: str) -> dict[str, Any]:
    non_null = series.dropna()
    result: dict[str, Any] = {
        "name": name,
        "dtype": str(series.dtype),
        "null_count": int(series.isna().sum()),
        "null_ratio": round(float(series.isna().mean()), 4),
        "unique_count": int(non_null.nunique(dropna=True)),
        "samples": [_safe_scalar(value) for value in non_null.head(3).tolist()],
    }
    if pd.api.types.is_numeric_dtype(series) and len(non_null) > 0:
        result["numeric"] = {
            "min": _safe_scalar(non_null.min()),
            "max": _safe_scalar(non_null.max()),
            "mean": _safe_scalar(non_null.mean()),
            "sum": _safe_scalar(non_null.sum()),
        }
    temporal = _datetime_summary(series, name)
    if temporal:
        result["datetime"] = temporal
    if 0 < result["unique_count"] <= 20:
        top = non_null.astype(str).value_counts().head(5)
        result["top_values"] = [{"value": str(value), "count": int(count)} for value, count in top.items()]
    return result


def inspect_uploads(uploads_dir: Path, filenames: list[str] | None = None, sample_rows: int = 5) -> dict[str, Any]:
    """Inspect supported files in an uploads directory."""
    if not 1 <= sample_rows <= 10:
        raise StoreDataError("sample_rows 必须在 1 到 10 之间。")
    tables, sources = _load_tables(uploads_dir, filenames)
    source_by_alias = {item["alias"]: item for item in sources}
    table_reports: list[dict[str, Any]] = []
    all_roles: dict[str, list[str]] = {}
    for alias, frame in tables.items():
        roles = _semantic_roles(str(column) for column in frame.columns)
        for role, columns in roles.items():
            all_roles.setdefault(role, []).extend(f"{alias}.{column}" for column in columns)
        source = source_by_alias[alias]
        table_reports.append(
            {
                **source,
                "row_count": int(len(frame)),
                "column_count": int(len(frame.columns)),
                "duplicate_row_count": int(frame.duplicated().sum()),
                "columns": [_column_profile(frame[column], str(column)) for column in frame.columns],
                "semantic_roles": roles,
                "sample_rows": _safe_records(frame.head(sample_rows)),
            }
        )
    return {
        "ok": True,
        "table_count": len(table_reports),
        "tables": table_reports,
        "available_semantic_roles": all_roles,
        "sql_guidance": "后续使用 store_query_data；表名使用 alias，中文或含空格列名用双引号包裹。",
    }


def _validate_sql(sql: str) -> str:
    normalized = sql.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if not normalized or not _SQL_START_RE.match(normalized):
        raise StoreDataError("只允许执行 SELECT 或 WITH 开头的只读查询。")
    if ";" in normalized or "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise StoreDataError("查询只能包含一条语句，且不能包含 SQL 注释。")
    match = _FORBIDDEN_SQL_RE.search(normalized)
    if match:
        raise StoreDataError(f"查询包含不允许的只读边界外操作：{match.group(1)}")
    return normalized


def query_uploads(
    uploads_dir: Path,
    sql: str,
    filenames: list[str] | None = None,
    max_rows: int = 100,
) -> dict[str, Any]:
    """Execute bounded read-only SQL over uploaded tables."""
    if not 1 <= max_rows <= MAX_RESULT_ROWS:
        raise StoreDataError(f"max_rows 必须在 1 到 {MAX_RESULT_ROWS} 之间。")
    normalized_sql = _validate_sql(sql)
    tables, sources = _load_tables(uploads_dir, filenames)
    connection = duckdb.connect(database=":memory:", config={"enable_external_access": "false"})
    try:
        for alias, frame in tables.items():
            connection.register(alias, frame)
        bounded_sql = f"SELECT * FROM ({normalized_sql}) AS store_query_result LIMIT {max_rows + 1}"
        result = connection.execute(bounded_sql).fetchdf()
    except duckdb.Error as exc:
        raise StoreDataError(f"SQL 查询失败：{exc}") from exc
    finally:
        connection.close()
    truncated = len(result) > max_rows
    if truncated:
        result = result.head(max_rows)
    return {
        "ok": True,
        "tables": sources,
        "columns": [str(column) for column in result.columns],
        "row_count": int(len(result)),
        "truncated": truncated,
        "rows": _safe_records(result),
    }


@tool("store_inspect_data", parse_docstring=True)
def store_inspect_data_tool(
    runtime: Runtime,
    filenames: list[str] | None = None,
    sample_rows: int = 5,
) -> str:
    """检查当前对话上传的 CSV/XLSX 数据结构、质量、时间和可分析字段。

    在分析店铺数据前先调用本工具。它会返回每张表的 alias、行列数、字段类型、
    空值、重复行、样例和可能的订单/时间/金额/商品等语义字段。后续 SQL 必须使用
    返回的 alias；中文列名或包含空格的列名需要用双引号包裹。

    Args:
        filenames: 可选的上传文件名列表；省略时检查当前对话中的全部 CSV/XLSX。
        sample_rows: 每张表返回的样例行数，范围 1-10。
    """
    try:
        return _json_dumps(inspect_uploads(_uploads_dir(runtime), filenames, sample_rows))
    except StoreDataError as exc:
        return _json_dumps({"ok": False, "error": str(exc)})


@tool("store_query_data", parse_docstring=True)
def store_query_data_tool(
    runtime: Runtime,
    sql: str,
    filenames: list[str] | None = None,
    max_rows: int = 100,
) -> str:
    """使用 DuckDB 对当前对话上传的 CSV/XLSX 执行一条受限只读 SQL 查询。

    只接受 SELECT/WITH 查询，禁止读取上传目录之外的文件，也禁止写入、安装扩展、
    ATTACH、COPY 或多语句。先调用 store_inspect_data 获取表 alias 和真实列名；
    所有经营指标、窗口比较、分组聚合和贡献拆解都应通过本工具计算，不要让模型心算。

    Args:
        sql: 单条 SELECT 或 WITH 查询。
        filenames: 可选的上传文件名列表；省略时加载全部 CSV/XLSX。
        max_rows: 最大返回行数，范围 1-200。
    """
    try:
        return _json_dumps(query_uploads(_uploads_dir(runtime), sql, filenames, max_rows))
    except StoreDataError as exc:
        return _json_dumps({"ok": False, "error": str(exc)})
