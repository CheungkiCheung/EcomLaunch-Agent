"""Fresh, fail-closed DeepSeek V4 preflight for Store Operator acceptance.

This module makes one direct request to the configured official DeepSeek API.
It does not use LangChain cache, retry middleware, replay fixtures, or a fallback
model. The persisted record intentionally excludes prompts, responses and keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from dotenv import load_dotenv

MODEL_ALIAS = "deepseek-reasoner"
EXPECTED_PROVIDER = "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
OFFICIAL_HOST = "api.deepseek.com"
V4_IDENTITY = re.compile(r"^deepseek[-_]v4(?:$|[-_.])", re.IGNORECASE)
PROMPT_VERSION = "store-operator-real-model-preflight@1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config.yaml"
_DEFAULT_AUDIT_DIR = (
    _REPO_ROOT
    / ".deer-flow"
    / "store-operator"
    / "evaluation"
    / "real-model-preflight"
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _official_endpoint(api_base: str) -> bool:
    parsed = urlparse(api_base)
    return parsed.scheme == "https" and parsed.hostname == OFFICIAL_HOST


def _redact(message: str, secret: str | None = None) -> str:
    sanitized = message.replace(secret, "[REDACTED]") if secret else message
    sanitized = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s;,]+",
        r"\1[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)(api[_-]?key\s*[=:]\s*)[^\s;,]+",
        r"\1[REDACTED]",
        sanitized,
    )
    return " ".join(sanitized.split())[:1000]


def _load_model_config(config_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = payload.get("models") or []
    model = next(
        (
            item
            for item in models
            if isinstance(item, dict) and item.get("name") == MODEL_ALIAS
        ),
        None,
    )
    if not isinstance(model, dict):
        raise ValueError(f"配置中缺少模型 alias：{MODEL_ALIAS}")
    return model


def _base_result(model: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "checked_at": datetime.now(UTC).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "configured_alias": MODEL_ALIAS,
        "configured_model": str(model.get("model") or "<missing>"),
        "provider_class": str(model.get("use") or "<missing>"),
        "endpoint": str(model.get("api_base") or model.get("base_url") or ""),
        "configured_max_retries": model.get("max_retries"),
        "request_attempt_count": 0,
        "retry_count": 0,
    }


def _persist(result: dict[str, Any], audit_dir: Path) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{result['run_id']}.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run_real_model_preflight(
    *,
    config_path: Path = _DEFAULT_CONFIG,
    audit_dir: Path = _DEFAULT_AUDIT_DIR,
) -> tuple[dict[str, Any], Path]:
    """Execute exactly one fresh provider request and persist secret-free evidence."""

    load_dotenv(_REPO_ROOT / ".env", override=False)
    run_id = f"preflight-{uuid.uuid4().hex}"
    try:
        model = _load_model_config(config_path)
    except Exception as exc:
        result = {
            **_base_result({}, run_id),
            "status": "blocked_configuration",
            "error": _redact(str(exc)),
        }
        return result, _persist(result, audit_dir)

    result = _base_result(model, run_id)
    api_base = result["endpoint"]
    key_value = str(model.get("api_key") or "")
    env_name = key_value[1:] if key_value.startswith("$") else "DEEPSEEK_API_KEY"
    api_key = os.getenv(env_name) if key_value.startswith("$") else key_value

    configuration_errors: list[str] = []
    if result["configured_model"] != "deepseek-v4-flash":
        configuration_errors.append("configured_model 必须是 deepseek-v4-flash")
    if result["provider_class"] != EXPECTED_PROVIDER:
        configuration_errors.append("provider_class 不是 PatchedChatDeepSeek")
    if result["configured_max_retries"] != 0:
        configuration_errors.append("configured_max_retries 必须为 0")
    if not _official_endpoint(api_base):
        configuration_errors.append("endpoint 不是官方 DeepSeek HTTPS 地址")
    if not api_key:
        configuration_errors.append(f"环境变量 {env_name} 未配置")
    if configuration_errors:
        result.update(
            status="blocked_configuration",
            error="；".join(configuration_errors),
        )
        return result, _persist(result, audit_dir)

    challenge = f"STORE_V4_OK:{uuid.uuid4().hex}"
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=60.0, follow_redirects=False) as client:
            response = client.post(
                f"{api_base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": result["configured_model"],
                    "messages": [
                        {
                            "role": "system",
                            "content": "你正在执行连接预检，只输出用户给出的完整校验字符串。",
                        },
                        {"role": "user", "content": challenge},
                    ],
                    "temperature": 0,
                    "max_tokens": 256,
                    "stream": False,
                    "thinking": {"type": "disabled"},
                },
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        result.update(
            request_attempt_count=1,
            retry_count=0,
            latency_ms=latency_ms,
            http_status_code=response.status_code,
            request_nonce_sha256=_sha256(challenge),
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        result.update(
            status="blocked_provider_unavailable",
            request_attempt_count=1,
            retry_count=0,
            latency_ms=latency_ms,
            request_nonce_sha256=_sha256(challenge),
            error=_redact(str(exc), api_key),
        )
        return result, _persist(result, audit_dir)

    choices = payload.get("choices") if isinstance(payload, dict) else None
    first_choice = choices[0] if isinstance(choices, list) and choices else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    content = content if isinstance(content, str) else ""
    actual_identity = payload.get("model") if isinstance(payload, dict) else None
    response_id = payload.get("id") if isinstance(payload, dict) else None
    header_request_id = response.headers.get("x-request-id")
    provider_request_id = header_request_id or response_id
    request_id_source = "response_headers.x-request-id" if header_request_id else "response.id"
    usage = payload.get("usage") if isinstance(payload, dict) else None
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None

    result.update(
        actual_model_identity=actual_identity,
        identity_evidence_source="response.model",
        provider_request_id=provider_request_id,
        provider_request_id_source=request_id_source,
        provider_response_id=response_id,
        token_usage=usage if isinstance(usage, dict) else None,
        finish_reason=finish_reason,
        response_content_sha256=_sha256(content),
        challenge_echoed=challenge in content,
    )

    missing: list[str] = []
    if not isinstance(actual_identity, str) or not V4_IDENTITY.match(actual_identity):
        missing.append("服务端未返回 DeepSeek V4 模型身份")
    if not isinstance(provider_request_id, str) or not provider_request_id:
        missing.append("缺少 provider request ID")
    if not isinstance(response_id, str) or not response_id:
        missing.append("缺少 provider response ID")
    if not isinstance(usage, dict) or not isinstance(usage.get("total_tokens"), int):
        missing.append("缺少 provider token usage")
    if challenge not in content:
        missing.append("响应未回显本次随机校验字符串")

    if missing:
        result.update(status="blocked_identity_or_telemetry", error="；".join(missing))
    else:
        result["status"] = "passed"
    return result, _persist(result, audit_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fresh DeepSeek V4 preflight")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)
    parser.add_argument("--audit-dir", type=Path, default=_DEFAULT_AUDIT_DIR)
    args = parser.parse_args()
    result, path = run_real_model_preflight(
        config_path=args.config,
        audit_dir=args.audit_dir,
    )
    summary = {
        "status": result["status"],
        "actual_model_identity": result.get("actual_model_identity"),
        "configured_max_retries": result.get("configured_max_retries"),
        "retry_count": result.get("retry_count"),
        "provider_request_id": result.get("provider_request_id"),
        "audit_path": str(path),
        "error": result.get("error"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
