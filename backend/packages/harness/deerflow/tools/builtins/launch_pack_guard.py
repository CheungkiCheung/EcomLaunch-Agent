"""Deterministic preflight checks for configured multi-file launch packs."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

_NO_SAMPLE_PATTERN = re.compile(r"无样品|没有样品|无规格|没有规格|no\s+sample|no\s+spec", re.IGNORECASE)
_COMPACTED_WRITE_PLACEHOLDER_PATTERN = re.compile(
    r"^\s*\[compacted \d+ characters already written successfully to .*?; do not reread[^\]]*\]\s*$",
    re.IGNORECASE | re.DOTALL,
)
_FIRST_PERSON_EXPERIENCE_PATTERN = re.compile(
    r"(?:我|本人|我们).{0,18}(?:用过|用了|试过|试用|亲测|上手|体验|回购|入手|测过|最近看到|最近留意|最戳我|会考虑)",
    re.IGNORECASE,
)
_TESTIMONIAL_COPY_PATTERN = re.compile(r"用了就|用过就|一用就|试过就|回不去|离不开|真香|亲测|实测", re.IGNORECASE)
_NEGATED_TESTIMONIAL_PATTERN = re.compile(r"(?:非|未|无|不做|不是)\s*(?:亲测|实测|试用|体验)", re.IGNORECASE)
_USAGE_HISTORY_PATTERN = re.compile(
    r"用了\s*(?:[0-9一二三四五六七八九十两]+\s*(?:天|周|个?月|年)|一段时间)|用过\s*(?:好几|几|多)款",
    re.IGNORECASE,
)
_FEATURE_PATTERN = re.compile(
    r"Qi2?|\b\d+(?:\.\d+)?\s*W\b|\d{3,4}\s*(?:不锈钢|ml|毫升)|磁吸|自动对位|防滑|加重底座|底座加重|散热|不发烫|不烫|兼容|认证|吸力|双充|快充|温升|防泼水|防水|续航|食品级|保温|防漏|不锈钢|材质|材料|面料|容量|大容量|尺寸|重量|可机洗|洗碗机|防噎|耐摔|耐高温|无毒|抗菌|除菌|降噪|静音|防刮|耐磨|易清洗|人体工学|可调节|折叠|便携|牢固|稳定|车载|高颜值|好看|出片",
    re.IGNORECASE,
)
_PRODUCT_EXISTENCE_PATTERN = re.compile(
    r"这(?:只|款|台|件)(?!类|些)|这个(?:产品|商品|杯|用品|设备)|(?:我们|咱们)(?:的)?(?:产品|商品|新品)",
    re.IGNORECASE,
)
_FIRST_PERSON_PERSONA_PATTERN = re.compile(r"(?:本人|我)(?:是|就是|妥妥|作为).{0,12}(?:控|党|爱好者|用户|达人)", re.IGNORECASE)
_FORBIDDEN_LIST_PATTERN = re.compile(r"^\s*(?:[-*>#\d.、 ]*)?(?:禁用词|禁止词|敏感词|安全清单|forbidden\s+(?:terms|words))", re.IGNORECASE)
_INTERNAL_HYPOTHESIS_PREFIX = re.compile(r"^\s*(?:[-*>#\d.、 ]*)?(?:内部验证假设|验证假设|待验证|待确认项|需确认|未知|禁止|不得|不可|unavailable)", re.IGNORECASE)


def _is_direct_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_direct_evidence_url(value: object) -> bool:
    """Reject search/discovery pages that do not directly support a claim."""
    if not _is_direct_url(value):
        return False
    parsed = urlparse(str(value).strip())
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower().rstrip("/")
    if host in {"bing.com", "www.bing.com", "cn.bing.com"} and (path.startswith("/images/search") or path == "/search"):
        return False
    if host in {"google.com", "www.google.com", "google.com.hk", "www.google.com.hk"} and path in {"/search", "/images"}:
        return False
    if host in {"baidu.com", "www.baidu.com"} and path == "/s":
        return False
    if host in {"image.baidu.com", "images.baidu.com"} and path.startswith("/search"):
        return False
    return True


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _validate_evidence_ledger(path: Path) -> list[str]:
    try:
        payload = json.loads(_read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"evidence-ledger.json is not valid readable JSON: {exc}"]

    if not isinstance(payload, dict):
        return ["evidence-ledger.json must be a JSON object containing an entries array"]
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return ["evidence-ledger.json must contain an entries array"]

    issues: list[str] = []
    valid_labels = {"observed_public", "uploaded_real", "estimated", "assumption", "unavailable"}
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            issues.append(f"evidence-ledger.json entry {index} must be a JSON object")
            continue
        evidence_level = entry.get("label") or entry.get("evidence_label") or entry.get("evidence_level")
        if evidence_level not in valid_labels:
            entry_id = entry.get("id") or index
            issues.append(f"evidence-ledger.json entry {entry_id} has an invalid evidence label: {evidence_level or '[blank]'}")
            continue
        if evidence_level != "observed_public":
            continue
        urls = entry.get("source_urls")
        if not isinstance(urls, list) or not any(_is_direct_evidence_url(url) for url in urls):
            entry_id = entry.get("id") or index
            issues.append(f"evidence-ledger.json entry {entry_id} is observed_public without a direct evidence source_urls value")
    return issues


def _validate_competitor_table(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        return [f"competitor-table.csv is not readable: {exc}"]

    if not rows:
        return ["competitor-table.csv has no data rows"]
    fieldnames = set(rows[0])
    missing_columns: list[str] = []
    if "source_url" not in fieldnames:
        missing_columns.append("competitor-table.csv is missing the source_url column")
    if "evidence_label" not in fieldnames:
        missing_columns.append("competitor-table.csv is missing the evidence_label column")
    if missing_columns:
        return missing_columns

    issues: list[str] = []
    valid_labels = {"observed_public", "uploaded_real", "estimated", "assumption", "unavailable"}
    for row_number, row in enumerate(rows, start=2):
        evidence_label = str(row.get("evidence_label") or "").strip().lower()
        source_url = str(row.get("source_url") or "").strip()
        if evidence_label not in valid_labels:
            issues.append(f"competitor-table.csv row {row_number} has an invalid evidence_label: {evidence_label or '[blank]'}")
            continue
        if evidence_label == "observed_public" and not _is_direct_evidence_url(source_url):
            issues.append(f"competitor-table.csv row {row_number} is observed_public without a direct evidence source_url")
        elif source_url and not _is_direct_url(source_url):
            issues.append(f"competitor-table.csv row {row_number} has a non-http(s) source_url")
    return issues


def _validate_no_sample_consumer_copy(path: Path) -> list[str]:
    issues: list[str] = []
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _FORBIDDEN_LIST_PATTERN.search(stripped):
            issues.append(f"{path.name}:{line_number} contains an internal forbidden-term or safety-list section that must not appear in consumer copy: {stripped[:120]}")
            continue
        if _INTERNAL_HYPOTHESIS_PREFIX.search(stripped):
            continue
        testimonial_text = _NEGATED_TESTIMONIAL_PATTERN.sub("", stripped)
        if _FIRST_PERSON_EXPERIENCE_PATTERN.search(stripped) or _TESTIMONIAL_COPY_PATTERN.search(testimonial_text) or _USAGE_HISTORY_PATTERN.search(stripped):
            issues.append(f"{path.name}:{line_number} contains a first-person usage/testimonial pattern: {stripped[:120]}")
            continue
        if _FIRST_PERSON_PERSONA_PATTERN.search(stripped) or _PRODUCT_EXISTENCE_PATTERN.search(stripped):
            issues.append(f"{path.name}:{line_number} implies a product or consumer persona already exists in a no-sample concept test: {stripped[:120]}")
            continue
        if _FEATURE_PATTERN.search(stripped):
            issues.append(
                f"{path.name}:{line_number} states an unconfirmed product feature in consumer-facing copy; remove the entire line or replace it with a neutral user-problem question that retains none of its feature terms: {stripped[:120]}"
            )
    return issues


def _meaningful_text(content: str) -> str:
    """Strip formatting noise before applying conservative content thresholds."""
    without_embedded_code = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", content, flags=re.IGNORECASE | re.DOTALL)
    without_comments = re.sub(r"<!--.*?-->", " ", without_embedded_code, flags=re.DOTALL)
    without_markup = re.sub(r"<[^>]+>", " ", without_comments)
    without_markdown = re.sub(r"[`*_>#|~-]", " ", without_markup)
    return re.sub(r"\s+", " ", without_markdown).strip()


def _validate_effective_content(name: str, path: Path) -> list[str]:
    """Reject empty or structurally fake artifacts before delivery."""
    content = _read_text(path)
    if not content.strip():
        return [f"{name} is empty"]

    if name == "launch-war-room.html":
        missing_structure = [tag for tag in ("html", "body") if re.search(rf"<{tag}\b", content, re.IGNORECASE) is None]
        if missing_structure:
            missing_tags = " and ".join(f"<{tag}>" for tag in missing_structure)
            return [f"launch-war-room.html is missing real {missing_tags} structure"]
        if len(_meaningful_text(content)) < 32:
            return ["launch-war-room.html has no meaningful body content"]

    if path.suffix.lower() == ".md":
        meaningful = _meaningful_text(content)
        if len(meaningful) < 80 or len([line for line in content.splitlines() if line.strip()]) < 2:
            return [f"{name} is too small to be an effective Markdown deliverable"]

    if path.suffix.lower() == ".csv":
        try:
            rows = list(csv.reader(io.StringIO(content)))
        except csv.Error as exc:
            return [f"{name} is not readable CSV: {exc}"]
        nonempty_rows = [row for row in rows if any(cell.strip() for cell in row)]
        if len(nonempty_rows) < 2 or not any(cell.strip() for cell in nonempty_rows[1]):
            return [f"{name} must contain a header and at least one non-empty data row"]

    if name == "evidence-ledger.json":
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        entries = payload.get("entries") if isinstance(payload, dict) else payload
        if isinstance(entries, list) and not entries:
            return ["evidence-ledger.json entries must contain at least one effective record"]

    return []


def _concept_context(user_request: str) -> tuple[str, str]:
    price_match = re.search(r"(\d{1,5})\s*[-~至]\s*(\d{1,5})\s*元", user_request)
    price_text = f"{price_match.group(1)}-{price_match.group(2)} 元" if price_match else "用户给出的目标价"
    category_match = re.search(r"\d{1,5}\s*[-~至]\s*\d{1,5}\s*元的([^，。,.]{2,30})", user_request)
    category = category_match.group(1).strip() if category_match else "新品类"
    return category, price_text


def _safe_listing_template(user_request: str) -> str:
    category, price_text = _concept_context(user_request)
    return f"""# {category} Listing Pack（概念验证版）

> 阶段：无样品、无规格。本文件仅用于需求调研，不是可购买商品页，不接受订单或付款。

## 标题

{category}｜{price_text} 概念偏好调研

## 调研页面结构

### 1. 当前问题

- 你在选择或使用这一品类时，最希望先解决什么问题？
- 现有替代方案中，哪一点最影响你的选择？
- 哪个真实使用场景最值得优先验证？

### 2. 预算验证

- 对“{category}”这一品类，你可接受的预算区间是什么？
- 在 {price_text} 的目标范围内，哪个价格点值得继续研究？
- 哪些信息缺失时，你不会考虑进一步了解？

### 3. 优先级验证

请只按问题和场景排序：使用场景、整理习惯、购买时机、预算、现有替代方案。

### 4. 行动入口

- 填写匿名偏好问卷。
- 自愿登记后续研究通知；不承诺供货、价格、日期或产品能力。
- 不收定金，不创建虚假销量、评价、库存或倒计时。

## 发布边界

不得在取得样品、规格和测试证据前加入产品特性、材料、外观、尺寸、容量、性能、兼容性、安全、认证、测试结果、用户体验或保证性承诺。
"""


def _safe_content_template(user_request: str) -> str:
    category, price_text = _concept_context(user_request)
    return f"""# {category} Content Pack（概念调研版）

> 阶段：无样品、无规格。以下内容只收集问题、场景和预算偏好，不展示或暗示产品已经存在。

## 小红书问题帖 A

**标题：** 选这类用品时，你最想先解决哪个问题？

**正文：** 正在研究“{category}”这个品类。请只根据真实经历选择：现有替代方案哪里不顺手，哪个使用场景最需要改善，哪些信息会影响你的判断？本帖不售卖、不收款。

**互动：** 评论一个最困扰的问题；不征集好评或虚构体验。

## 小红书问题帖 B

**标题：** {price_text} 的品类概念，你会先看什么信息？

**正文：** 这是价格与信息需求调研。请选择最先需要确认的内容：真实使用场景、预算、购买时机、现有替代方案，或其他问题。这里没有可购买商品，也不接受预订。

**互动：** 选择一个优先项，并说明原因。

## 短视频口播

“这是一项关于 {category} 的概念调研。目标价范围是 {price_text}。请告诉我们：你最希望先解决什么问题，什么信息缺失时你不会继续了解？当前没有样品或可购买商品，不接受付款或预订。”

## 评论回复

- “目前只做需求调研，相关产品事实尚未确认。”
- “谢谢反馈；这条会作为待验证问题记录，不会当作已证实结论。”
- “当前不售卖、不收款，后续通知也不代表供货承诺。”

## 发布边界

不得加入产品特性、材料、外观、尺寸、容量、性能、兼容性、安全、认证、测试结果、用户体验、销量、评价、稀缺性或保证性承诺。
"""


def _normalize_ledger_sources(path: Path) -> bool:
    try:
        payload = json.loads(_read_text(path))
    except (OSError, json.JSONDecodeError):
        return False
    entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return False

    changed = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label_key = next((key for key in ("label", "evidence_label", "evidence_level") if key in entry), "label")
        if entry.get(label_key) != "observed_public":
            continue
        urls = entry.get("source_urls")
        if isinstance(urls, list) and any(_is_direct_evidence_url(url) for url in urls):
            continue
        entry[label_key] = "estimated"
        changed = True
    if changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def _normalize_competitor_sources(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames
    except OSError:
        return False
    if not rows or not fieldnames or "evidence_label" not in fieldnames or "source_url" not in fieldnames:
        return False

    changed = False
    for row in rows:
        if str(row.get("evidence_label") or "").strip().lower() != "observed_public":
            continue
        if _is_direct_evidence_url(row.get("source_url")):
            continue
        row["evidence_label"] = "estimated"
        changed = True
    if changed:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        path.write_text(buffer.getvalue(), encoding="utf-8")
    return changed


def prepare_launch_pack_for_audit(outputs_dir: Path, required_files: list[str], *, user_request: str = "") -> list[str]:
    """Apply deterministic evidence and no-sample normalization before black-box audit."""
    required = set(required_files)
    changed: list[str] = []
    no_sample_context = bool(_NO_SAMPLE_PATTERN.search(user_request))
    if not no_sample_context:
        no_sample_context = any(
            name in required
            and (path := outputs_dir / name).is_file()
            and bool(_NO_SAMPLE_PATTERN.search(_read_text(path)))
            for name in ("listing-pack.md", "content-pack.md")
        )
    if no_sample_context:
        templates = {
            "listing-pack.md": _safe_listing_template(user_request),
            "content-pack.md": _safe_content_template(user_request),
        }
        for name, content in templates.items():
            path = outputs_dir / name
            if name in required and path.is_file() and _read_text(path) != content:
                path.write_text(content, encoding="utf-8")
                changed.append(name)

    ledger = outputs_dir / "evidence-ledger.json"
    if "evidence-ledger.json" in required and ledger.is_file() and _normalize_ledger_sources(ledger):
        changed.append("evidence-ledger.json")
    competitors = outputs_dir / "competitor-table.csv"
    if "competitor-table.csv" in required and competitors.is_file() and _normalize_competitor_sources(competitors):
        changed.append("competitor-table.csv")
    return changed


def validate_launch_pack(outputs_dir: Path, required_files: list[str], *, user_request: str = "") -> list[str]:
    """Return blocking issues for a complete configured launch pack."""
    issues: list[str] = []
    required_paths = {name: outputs_dir / name for name in required_files}
    for name, path in required_paths.items():
        if not path.is_file():
            issues.append(f"required output file is missing: {name}")
    if issues:
        return issues

    for name, path in required_paths.items():
        if _COMPACTED_WRITE_PLACEHOLDER_PATTERN.fullmatch(_read_text(path)):
            issues.append(f"{name} contains an internal history-compaction marker instead of artifact content")
        issues.extend(_validate_effective_content(name, path))
    ledger_path = required_paths.get("evidence-ledger.json")
    if ledger_path is not None:
        issues.extend(_validate_evidence_ledger(ledger_path))

    competitor_path = required_paths.get("competitor-table.csv")
    if competitor_path is not None:
        issues.extend(_validate_competitor_table(competitor_path))

    pack_text = "\n".join(_read_text(path) for path in required_paths.values() if path.suffix.lower() in {".md", ".json", ".html"})
    if _NO_SAMPLE_PATTERN.search(user_request) or _NO_SAMPLE_PATTERN.search(pack_text):
        for name in ("listing-pack.md", "content-pack.md"):
            consumer_path = required_paths.get(name)
            if consumer_path is not None:
                issues.extend(_validate_no_sample_consumer_copy(consumer_path))

    return issues[:30]
