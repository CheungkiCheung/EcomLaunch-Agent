"""Deterministic, read-only analysis tools for uploaded CSV/XLSX files.

The Growth Analyst agent is configured through OpenSKU's native agent, skill,
and tool configuration.  This module deliberately stays small: it resolves the
current thread's upload directory, profiles supported tabular files, and runs a
single bounded read-only DuckDB query over in-memory tables.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from statistics import NormalDist
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
SAMPLE_RATIO_MISMATCH_THRESHOLD = 0.001

_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]+")
_SQL_START_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN_SQL_RE = re.compile(
    r"\b(attach|copy|install|load|pragma|create|update|insert|delete|drop|alter|"
    r"export|import|call|set|read_csv|read_csv_auto|read_parquet|parquet_scan|"
    r"read_json|read_json_auto|read_ndjson|read_text|read_blob|glob|sniff_csv|"
    r"sqlite_scan|postgres_scan|mysql_scan|delta_scan|iceberg_scan|httpfs|http_get)\b",
    re.IGNORECASE,
)
_TIME_NAME_HINTS = (
    "date",
    "time",
    "created",
    "updated",
    "published",
    "日期",
    "时间",
    "下单",
    "支付",
    "发布",
)
_FREE_TEXT_NAME_HINTS = (
    "comment",
    "message",
    "description",
    "caption",
    "content",
    "body",
    "review_text",
    "评论",
    "留言",
    "描述",
    "正文",
    "文案",
)


class DataInspectorError(ValueError):
    """A user-correctable uploaded-data or query error."""


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
    if isinstance(value, (str, int, float, bool)):
        return value
    return _json_default(value)


def _safe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(key): _safe_scalar(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _inspect_sample_scalar(value: Any) -> Any:
    safe_value = _safe_scalar(value)
    if isinstance(safe_value, str) and len(safe_value) > 160:
        return f"{safe_value[:157]}..."
    return safe_value


def _is_free_text_column(name: str, series: pd.Series) -> bool:
    normalized = name.lower()
    if normalized == "id" or normalized.endswith("_id"):
        return False
    return (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)) and any(hint in normalized for hint in _FREE_TEXT_NAME_HINTS)


def _inspect_sample_records(frame: pd.DataFrame, *, include_text_samples: bool) -> list[dict[str, Any]]:
    free_text_columns = {str(column) for column in frame.columns if _is_free_text_column(str(column), frame[column])}
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        record: dict[str, Any] = {}
        for key, value in row.items():
            key_str = str(key)
            safe_value = _safe_scalar(value)
            if not include_text_samples and key_str in free_text_columns and safe_value is not None:
                record[key_str] = "[text omitted]"
            else:
                record[key_str] = _inspect_sample_scalar(value)
        records.append(record)
    return records


def _uploads_dir(runtime: Runtime) -> Path:
    state = runtime.state or {}
    thread_data = state.get("thread_data") or {}
    raw_path = thread_data.get("uploads_path")
    if not raw_path:
        raise DataInspectorError("当前对话没有可访问的上传目录。请先上传 CSV 或 XLSX 文件。")
    path = Path(raw_path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _supported_files(uploads_dir: Path, filenames: list[str] | None) -> list[Path]:
    requested = filenames or [path.name for path in sorted(uploads_dir.iterdir()) if path.is_file()]
    files: list[Path] = []
    seen: set[str] = set()

    for raw_name in requested:
        raw_path = Path(raw_name)
        if raw_name.startswith("/mnt/user-data/uploads/"):
            name = raw_path.name
        elif raw_path.name == raw_name:
            name = raw_name
        else:
            raise DataInspectorError(f"不允许读取上传目录之外的路径：{raw_name}")

        candidate = (uploads_dir / name).resolve()
        try:
            candidate.relative_to(uploads_dir)
        except ValueError as exc:
            raise DataInspectorError(f"不允许读取上传目录之外的路径：{raw_name}") from exc

        if candidate.name in seen:
            continue
        if not candidate.is_file():
            raise DataInspectorError(f"未找到上传文件：{candidate.name}")
        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            if filenames is not None:
                raise DataInspectorError(f"暂不支持 {candidate.suffix or '无扩展名'} 文件：{candidate.name}。请上传 CSV 或 XLSX。")
            continue
        if candidate.stat().st_size > MAX_FILE_BYTES:
            raise DataInspectorError(f"文件 {candidate.name} 超过 50 MB，当前版本暂不支持。")

        seen.add(candidate.name)
        files.append(candidate)

    if not files:
        raise DataInspectorError("没有找到可分析的 CSV 或 XLSX 文件。请先上传数据。")
    return files


def _identifier(value: str, fallback: str) -> str:
    normalized = _IDENTIFIER_RE.sub("_", value.strip()).strip("_").lower()
    if not normalized or normalized[0].isdigit():
        return fallback
    return normalized[:64]


def _unique_name(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    used: set[str] = set()
    columns: list[str] = []
    for index, raw_column in enumerate(normalized.columns, start=1):
        base = str(raw_column).strip() or f"column_{index}"
        columns.append(_unique_name(base, used))
    normalized.columns = columns
    return normalized


def _coerce_datetime_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.columns:
        series = normalized[column]
        column_name = str(column).lower()
        if not any(hint in column_name for hint in _TIME_NAME_HINTS):
            continue
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        non_null_count = int(series.notna().sum())
        if non_null_count == 0:
            continue
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        if int(converted.notna().sum()) / non_null_count >= 0.9:
            normalized[column] = converted
    return normalized


def _detect_alternate_csv_delimiter(path: Path, encoding: str) -> str | None:
    with path.open("r", encoding=encoding, newline="") as stream:
        sample = stream.read(64 * 1024)

    first_non_empty_line = next((line for line in sample.splitlines() if line.strip()), None)
    if first_non_empty_line is None:
        return None

    candidates: list[tuple[int, str]] = []
    for delimiter in ("\t", ";", "|"):
        try:
            column_count = len(next(csv.reader([first_non_empty_line], delimiter=delimiter)))
        except csv.Error:
            continue
        if column_count > 1:
            candidates.append((column_count, delimiter))

    if not candidates:
        return None
    return max(candidates)[1]


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            frame = pd.read_csv(path, encoding=encoding, nrows=MAX_TABLE_ROWS + 1)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except pd.errors.EmptyDataError as exc:
            raise DataInspectorError(f"CSV 文件 {path.name} 为空或没有可读取的列。") from exc
        except pd.errors.ParserError as exc:
            last_error = exc
            delimiter = _detect_alternate_csv_delimiter(path, encoding)
            if delimiter is None:
                continue
            try:
                return pd.read_csv(path, encoding=encoding, sep=delimiter, nrows=MAX_TABLE_ROWS + 1)
            except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                last_error = exc
            continue

        if len(frame.columns) == 1:
            delimiter = _detect_alternate_csv_delimiter(path, encoding)
            if delimiter is not None:
                try:
                    return pd.read_csv(path, encoding=encoding, sep=delimiter, nrows=MAX_TABLE_ROWS + 1)
                except pd.errors.ParserError as exc:
                    last_error = exc
                    continue
        return frame
    raise DataInspectorError(f"无法读取 CSV 文件 {path.name}：{last_error}")


def _load_tables(uploads_dir: Path, filenames: list[str] | None = None) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    tables: dict[str, pd.DataFrame] = {}
    sources: list[dict[str, Any]] = []
    aliases: set[str] = set()

    for file_index, path in enumerate(_supported_files(uploads_dir, filenames), start=1):
        if path.suffix.lower() == ".csv":
            frame = _coerce_datetime_columns(_normalize_columns(_read_csv(path)))
            alias = _unique_name(_identifier(path.stem, f"table_{file_index}"), aliases)
            tables[alias] = frame
            sources.append({"alias": alias, "filename": path.name, "sheet": None})
            continue

        try:
            workbook = pd.ExcelFile(path, engine="openpyxl")
        except Exception as exc:
            raise DataInspectorError(f"无法读取 Excel 文件 {path.name}：{exc}") from exc

        for sheet_index, sheet_name in enumerate(workbook.sheet_names, start=1):
            try:
                frame = pd.read_excel(workbook, sheet_name=sheet_name, nrows=MAX_TABLE_ROWS + 1)
            except Exception as exc:
                raise DataInspectorError(f"无法读取 {path.name} 的工作表 {sheet_name}：{exc}") from exc
            frame = _coerce_datetime_columns(_normalize_columns(frame))
            base = _identifier(f"{path.stem}_{sheet_name}", f"table_{file_index}_{sheet_index}")
            alias = _unique_name(base, aliases)
            tables[alias] = frame
            sources.append({"alias": alias, "filename": path.name, "sheet": sheet_name})

    for alias, frame in tables.items():
        if len(frame.columns) > MAX_COLUMNS:
            raise DataInspectorError(f"数据表 {alias} 有 {len(frame.columns)} 列，超过当前 120 列限制。")
        if len(frame) > MAX_TABLE_ROWS:
            raise DataInspectorError(f"数据表 {alias} 超过当前 30 万行限制，请先拆分或抽样。")

    return tables, sources


def _datetime_summary(series: pd.Series, column_name: str) -> dict[str, Any] | None:
    normalized_name = column_name.lower()
    if not pd.api.types.is_datetime64_any_dtype(series) and not any(hint in normalized_name for hint in _TIME_NAME_HINTS):
        return None
    converted = pd.to_datetime(series, errors="coerce")
    non_null_count = int(series.notna().sum())
    parsed_count = int(converted.notna().sum())
    if non_null_count == 0 or parsed_count / non_null_count < 0.6:
        return None
    return {
        "parsed_ratio": round(parsed_count / non_null_count, 4),
        "min": _safe_scalar(converted.min()),
        "max": _safe_scalar(converted.max()),
    }


def _column_profile(series: pd.Series, name: str) -> dict[str, Any]:
    non_null = series.dropna()
    profile: dict[str, Any] = {
        "name": name,
        "dtype": str(series.dtype),
        "null_count": int(series.isna().sum()),
        "null_ratio": round(float(series.isna().mean()), 4),
        "unique_count": int(non_null.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(series) and len(non_null) > 0:
        profile["numeric"] = {
            "min": _safe_scalar(non_null.min()),
            "max": _safe_scalar(non_null.max()),
            "mean": _safe_scalar(non_null.mean()),
        }
    datetime_summary = _datetime_summary(series, name)
    if datetime_summary is not None:
        profile["datetime"] = datetime_summary
    if 0 < profile["unique_count"] <= 20:
        top_values = non_null.astype(str).value_counts().head(5)
        profile["top_values"] = [{"value": str(value), "count": int(count)} for value, count in top_values.items()]
    return profile


def inspect_uploads(uploads_dir: Path, filenames: list[str] | None = None, sample_rows: int = 3, include_text_samples: bool = False) -> dict[str, Any]:
    """Inspect uploaded tabular files and return stable table aliases and profiles."""
    if not 1 <= sample_rows <= 3:
        raise DataInspectorError("sample_rows 必须在 1 到 3 之间。")

    tables, sources = _load_tables(uploads_dir, filenames)
    source_by_alias = {source["alias"]: source for source in sources}
    table_reports: list[dict[str, Any]] = []
    for alias, frame in tables.items():
        table_reports.append(
            {
                **source_by_alias[alias],
                "row_count": int(len(frame)),
                "column_count": int(len(frame.columns)),
                "duplicate_row_count": int(frame.duplicated().sum()),
                "columns": [_column_profile(frame[column], str(column)) for column in frame.columns],
                "sample_rows": _inspect_sample_records(frame.head(sample_rows), include_text_samples=include_text_samples),
            }
        )

    return {
        "ok": True,
        "table_count": len(table_reports),
        "tables": table_reports,
        "sql_guidance": "后续调用 query_data；SQL 表名使用 alias，中文或含空格的列名用双引号包裹。",
    }


def _validate_sql(sql: str) -> str:
    normalized = sql.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if not normalized or not _SQL_START_RE.match(normalized):
        raise DataInspectorError("只允许执行 SELECT 或 WITH 开头的只读查询。")
    if ";" in normalized or "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise DataInspectorError("查询只能包含一条语句，且不能包含 SQL 注释。")
    forbidden = _FORBIDDEN_SQL_RE.search(normalized)
    if forbidden:
        raise DataInspectorError(f"查询包含不允许的操作：{forbidden.group(1)}")
    return normalized


def query_uploads(uploads_dir: Path, sql: str, filenames: list[str] | None = None, max_rows: int = 100) -> dict[str, Any]:
    """Execute one bounded read-only DuckDB query over uploaded tables."""
    if not 1 <= max_rows <= MAX_RESULT_ROWS:
        raise DataInspectorError(f"max_rows 必须在 1 到 {MAX_RESULT_ROWS} 之间。")

    normalized_sql = _validate_sql(sql)
    tables, sources = _load_tables(uploads_dir, filenames)
    connection = duckdb.connect(database=":memory:", config={"enable_external_access": "false", "threads": "2", "memory_limit": "512MB"})
    try:
        for alias, frame in tables.items():
            connection.register(alias, frame)
        bounded_sql = f"SELECT * FROM ({normalized_sql}) AS data_query_result LIMIT {max_rows + 1}"
        result = connection.execute(bounded_sql).fetchdf()
    except duckdb.Error as exc:
        available_tables = ", ".join(source["alias"] for source in sources)
        raise DataInspectorError(f"SQL 查询失败：{exc}。可用表：{available_tables}") from exc
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
        "query_executed": True,
        "rows": _safe_records(result),
    }


def analyze_binary_ab_test(
    control_visitors: int,
    control_conversions: int,
    variant_visitors: int,
    variant_conversions: int,
    confidence_level: float = 0.95,
    expected_control_share: float = 0.5,
) -> dict[str, Any]:
    """Analyze one control-versus-variant binary conversion experiment."""
    counts = {
        "control_visitors": control_visitors,
        "control_conversions": control_conversions,
        "variant_visitors": variant_visitors,
        "variant_conversions": variant_conversions,
    }
    for name, value in counts.items():
        if type(value) is not int:
            raise DataInspectorError(f"{name} 必须是整数。")
        if value < 0:
            raise DataInspectorError(f"{name} 不能为负数。")

    if control_visitors == 0 or variant_visitors == 0:
        raise DataInspectorError("control_visitors 和 variant_visitors 必须大于 0。")
    if control_conversions > control_visitors:
        raise DataInspectorError("control_conversions 不能大于 control_visitors。")
    if variant_conversions > variant_visitors:
        raise DataInspectorError("variant_conversions 不能大于 variant_visitors。")
    if isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float)):
        raise DataInspectorError("confidence_level 必须是 0.8 到 1.0 之间的小数。")
    if not 0.8 <= confidence_level < 1.0:
        raise DataInspectorError("confidence_level 必须大于等于 0.8 且小于 1.0。")
    if isinstance(expected_control_share, bool) or not isinstance(expected_control_share, (int, float)):
        raise DataInspectorError("expected_control_share 必须是 0 到 1 之间的小数。")
    if not 0 < expected_control_share < 1:
        raise DataInspectorError("expected_control_share 必须大于 0 且小于 1。")

    control_rate = control_conversions / control_visitors
    variant_rate = variant_conversions / variant_visitors
    absolute_difference = variant_rate - control_rate
    relative_lift = None if control_rate == 0 else absolute_difference / control_rate

    total_visitors = control_visitors + variant_visitors
    pooled_rate = (control_conversions + variant_conversions) / total_visitors
    pooled_variance = pooled_rate * (1 - pooled_rate) * (1 / control_visitors + 1 / variant_visitors)
    if pooled_variance == 0:
        z_score = 0.0
        p_value = 1.0
    else:
        z_score = absolute_difference / math.sqrt(pooled_variance)
        p_value = math.erfc(abs(z_score) / math.sqrt(2))

    alpha = 1 - confidence_level
    critical_value = NormalDist().inv_cdf(1 - alpha / 2)
    unpooled_variance = control_rate * (1 - control_rate) / control_visitors + variant_rate * (1 - variant_rate) / variant_visitors
    margin = critical_value * math.sqrt(unpooled_variance)

    expected_control = total_visitors * expected_control_share
    expected_variant = total_visitors * (1 - expected_control_share)
    sample_ratio_chi_square = (control_visitors - expected_control) ** 2 / expected_control + (variant_visitors - expected_variant) ** 2 / expected_variant
    sample_ratio_mismatch_p_value = math.erfc(math.sqrt(sample_ratio_chi_square / 2))

    return {
        "ok": True,
        "method": "two_sided_two_proportion_z_test",
        "confidence_level": confidence_level,
        **counts,
        "control_rate": control_rate,
        "variant_rate": variant_rate,
        "absolute_difference": absolute_difference,
        "relative_lift": relative_lift,
        "z_score": z_score,
        "p_value": p_value,
        "confidence_interval": {
            "lower": absolute_difference - margin,
            "upper": absolute_difference + margin,
        },
        "significant": p_value < alpha,
        "expected_control_share": expected_control_share,
        "observed_control_share": control_visitors / total_visitors,
        "sample_ratio_mismatch_p_value": sample_ratio_mismatch_p_value,
        "sample_ratio_mismatch_detected": sample_ratio_mismatch_p_value < SAMPLE_RATIO_MISMATCH_THRESHOLD,
        "sample_ratio_mismatch_threshold": SAMPLE_RATIO_MISMATCH_THRESHOLD,
    }


@tool("inspect_data", parse_docstring=True)
def inspect_data_tool(runtime: Runtime, filenames: list[str] | None = None, sample_rows: int = 3, include_text_samples: bool = False) -> str:
    """检查当前对话上传的 CSV/XLSX 表结构、数据质量、字段样例和时间范围。

    在首次分析或上传文件变化后先调用。返回每张表的稳定 alias、来源文件、Sheet、
    行列数、空值、重复行、字段类型、数值摘要和样例。自由文本样例默认隐藏，只有用户
    明确要求分析文本内容时才启用。后续 query_data 必须使用返回的 alias；中文或含空格
    的列名需要用双引号包裹。

    Args:
        filenames: 可选的上传文件名列表；省略时检查当前对话中的全部 CSV/XLSX。
        sample_rows: 每张表返回的样例行数，范围 1-3；超长文本会截断。
        include_text_samples: 是否显示评论、留言、描述等自由文本样例；默认 false。
    """
    try:
        return _json_dumps(inspect_uploads(_uploads_dir(runtime), filenames, sample_rows, include_text_samples))
    except DataInspectorError as exc:
        return _json_dumps({"ok": False, "error": str(exc)})


@tool("query_data", parse_docstring=True)
def query_data_tool(runtime: Runtime, sql: str, filenames: list[str] | None = None, max_rows: int = 100) -> str:
    """对当前对话上传的 CSV/XLSX 执行一条受限、只读的 DuckDB SQL 查询。

    只接受 SELECT/WITH 查询，禁止外部文件读取、网络访问、多语句和写操作。先调用
    inspect_data 获取表 alias 和真实列名。计数、聚合、比率、趋势、窗口比较、Join 和
    贡献拆解都应通过本工具计算，不要让模型根据样例行心算。

    Args:
        sql: 单条 SELECT 或 WITH 查询。
        filenames: 可选的上传文件名列表；省略时加载当前对话中的全部 CSV/XLSX。
        max_rows: 最大返回行数，范围 1-200。
    """
    try:
        return _json_dumps(query_uploads(_uploads_dir(runtime), sql, filenames, max_rows))
    except DataInspectorError as exc:
        return _json_dumps({"ok": False, "error": str(exc)})


@tool("analyze_ab_test", parse_docstring=True)
def analyze_ab_test_tool(
    control_visitors: int,
    control_conversions: int,
    variant_visitors: int,
    variant_conversions: int,
    confidence_level: float = 0.95,
    expected_control_share: float = 0.5,
) -> str:
    """确定性分析一个对照组与一个实验组的二元转化率 A/B 实验。

    返回两组转化率、绝对差、相对提升、双侧二比例 z 检验、差值置信区间和
    样本比例失配（SRM）检查。原始明细数据应先用 query_data 按随机化单元去重汇总；
    本工具不支持连续指标、多实验组、序贯检验，也不替代护栏指标和实验设计检查。

    Args:
        control_visitors: 对照组独立随机化单元数量，必须大于 0。
        control_conversions: 对照组转化数量，范围 0 到 control_visitors。
        variant_visitors: 实验组独立随机化单元数量，必须大于 0。
        variant_conversions: 实验组转化数量，范围 0 到 variant_visitors。
        confidence_level: 双侧置信水平，小数形式，默认 0.95。
        expected_control_share: 预期分给对照组的流量占比，默认 0.5。
    """
    try:
        return _json_dumps(
            analyze_binary_ab_test(
                control_visitors=control_visitors,
                control_conversions=control_conversions,
                variant_visitors=variant_visitors,
                variant_conversions=variant_conversions,
                confidence_level=confidence_level,
                expected_control_share=expected_control_share,
            )
        )
    except DataInspectorError as exc:
        return _json_dumps({"ok": False, "error": str(exc)})
