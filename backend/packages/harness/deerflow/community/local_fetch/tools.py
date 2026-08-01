import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from langchain.tools import tool
from scrapling.parser import Adaptor

from deerflow.config import get_app_config
from deerflow.utils.readability import ReadabilityExtractor

readability_extractor = ReadabilityExtractor()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalFetchConfig:
    timeout: int = 15
    render_timeout: int = 25
    max_chars: int = 4096
    min_content_chars: int = 600
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    proxy: str | None = None
    trust_env: bool = False
    render_mode: str = "auto"
    wait_until: str = "domcontentloaded"
    render_wait_ms: int = 1200
    block_resources: bool = True


RENDER_MODES = {"auto", "always", "never"}
WAIT_UNTIL_VALUES = {"commit", "domcontentloaded", "load", "networkidle"}


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_proxy(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    proxy = value.strip()
    return proxy or None


def _coerce_user_agent(value: object, default: str) -> str:
    if not isinstance(value, str):
        return default
    user_agent = value.strip()
    return user_agent or default


def _coerce_choice(value: object, default: str, choices: set[str]) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    return normalized if normalized in choices else default


def _load_config() -> LocalFetchConfig:
    config = LocalFetchConfig()
    tool_config = get_app_config().get_tool_config("web_fetch")
    if tool_config is None:
        return config

    extra = tool_config.model_extra
    return LocalFetchConfig(
        timeout=_coerce_int(extra.get("timeout"), config.timeout),
        render_timeout=_coerce_int(extra.get("render_timeout"), config.render_timeout),
        max_chars=_coerce_int(extra.get("max_chars"), config.max_chars),
        min_content_chars=_coerce_int(extra.get("min_content_chars"), config.min_content_chars),
        user_agent=_coerce_user_agent(extra.get("user_agent"), config.user_agent),
        proxy=_coerce_proxy(extra.get("proxy")),
        trust_env=_coerce_bool(extra.get("trust_env"), config.trust_env),
        render_mode=_coerce_choice(extra.get("render_mode"), config.render_mode, RENDER_MODES),
        wait_until=_coerce_choice(extra.get("wait_until"), config.wait_until, WAIT_UNTIL_VALUES),
        render_wait_ms=_coerce_int(extra.get("render_wait_ms"), config.render_wait_ms),
        block_resources=_coerce_bool(extra.get("block_resources"), config.block_resources),
    )


def _validate_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "URLs must include http:// or https:// and a valid host"
    return None


async def _fetch_html(url: str, config: LocalFetchConfig) -> tuple[str, str]:
    headers = {"User-Agent": config.user_agent, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8"}
    client_kwargs: dict[str, object] = {"follow_redirects": True, "trust_env": config.trust_env}
    if config.proxy:
        client_kwargs["proxy"] = config.proxy

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url, headers=headers, timeout=config.timeout)
    except httpx.HTTPError as exc:
        return "", f"Error: Local fetch request failed: {type(exc).__name__}: {exc}"

    if response.status_code >= 400:
        return "", f"Error: Local fetch returned status {response.status_code}: {response.text[:240]}"

    if not response.text or not response.text.strip():
        return "", "Error: Local fetch returned empty response"

    return response.text, ""


async def _fetch_rendered_html(url: str, config: LocalFetchConfig) -> tuple[str, str]:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError:
        return "", "Error: Playwright is not installed. Run `uv sync` and `uv run playwright install chromium`."

    try:
        async with async_playwright() as playwright:
            browser = None
            context = None
            page = None
            try:
                browser = await playwright.chromium.launch(headless=True)
                context_kwargs: dict[str, object] = {
                    "user_agent": config.user_agent,
                    "viewport": {"width": 1365, "height": 900},
                    "ignore_https_errors": True,
                }
                if config.proxy:
                    context_kwargs["proxy"] = {"server": config.proxy}

                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()

                if config.block_resources:

                    async def block_heavy_resources(route):
                        try:
                            if route.request.resource_type in {"font", "image", "media"}:
                                await route.abort()
                            else:
                                await route.continue_()
                        except PlaywrightError:
                            logger.debug("Ignoring Playwright route handler failure during fetch cleanup", exc_info=True)

                    await page.route("**/*", block_heavy_resources)

                timeout_ms = max(config.render_timeout, 1) * 1000
                try:
                    response = await page.goto(url, wait_until=config.wait_until, timeout=timeout_ms)
                except PlaywrightTimeoutError:
                    html = await page.content()
                    if html and html.strip():
                        return html, ""
                    return "", f"Error: Playwright render timed out after {config.render_timeout}s"

                if response and response.status >= 400:
                    return "", f"Error: Playwright render returned status {response.status}"

                if config.render_wait_ms > 0:
                    await page.wait_for_timeout(config.render_wait_ms)

                html = await page.content()
                if not html or not html.strip():
                    return "", "Error: Playwright render returned empty response"

                return html, ""
            finally:
                # Keep Playwright alive until its route callbacks and pages are
                # released. Closing these objects after leaving the manager can
                # strand Page._on_route tasks on the event loop.
                if page is not None:
                    try:
                        await page.unroute_all(behavior="ignoreErrors")
                    except PlaywrightError:
                        logger.debug("Ignoring Playwright unroute failure during fetch cleanup", exc_info=True)
                if context is not None:
                    try:
                        await context.close()
                    except PlaywrightError:
                        logger.debug("Ignoring Playwright context close failure during fetch cleanup", exc_info=True)
                if browser is not None:
                    try:
                        await browser.close()
                    except PlaywrightError:
                        logger.debug("Ignoring Playwright browser close failure during fetch cleanup", exc_info=True)
    except PlaywrightError as exc:
        return "", f"Error: Playwright render failed: {type(exc).__name__}: {exc}"


def _first_text(page: Adaptor, selector: str) -> str:
    value = page.css(selector).get()
    if value is None:
        return ""
    return str(value).strip()


def _fallback_body_text(page: Adaptor) -> str:
    chunks = []
    for raw in page.css("body ::text").getall():
        text = str(raw).strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _extract_markdown(html: str, url: str, max_chars: int) -> str:
    page = Adaptor(html, url=url)
    metadata_title = _first_text(page, "title::text")
    metadata_description = _first_text(page, 'meta[name="description"]::attr(content)')

    article = readability_extractor.extract_article(html)
    if article.title == "Untitled" and metadata_title:
        article.title = metadata_title

    markdown = article.to_markdown()
    if "No content could be extracted from this page" in markdown:
        body_text = _fallback_body_text(page)
        if body_text:
            title = metadata_title or "Untitled"
            markdown = f"# {title}\n\n{body_text}"

    if metadata_description and metadata_description not in markdown[:500]:
        markdown = markdown.replace("\n\n", f"\n\n> {metadata_description}\n\n", 1)

    return markdown[:max_chars]


def _meaningful_content_length(markdown: str) -> int:
    text = " ".join(line.strip() for line in markdown.splitlines() if line.strip() and not line.startswith(">"))
    return len(text)


def _should_try_render(markdown: str, config: LocalFetchConfig) -> bool:
    if config.render_mode != "auto":
        return False

    text = markdown.strip()
    lowered = text.lower()
    shell_markers = (
        "enable javascript",
        "please enable js",
        "please enable javascript",
        "requires javascript",
        "javascript is disabled",
        "__next_data__",
        "window.__",
        "app-root",
    )
    if any(marker in lowered for marker in shell_markers):
        return True

    return _meaningful_content_length(text) < config.min_content_chars


@tool("web_fetch", parse_docstring=True)
async def web_fetch_tool(url: str) -> str:
    """Fetch the contents of a web page at a given URL.
    Only fetch EXACT URLs that have been provided directly by the user or have been returned in results from the web_search and web_fetch tools.
    This tool can NOT access content that requires authentication, such as private Google Docs or pages behind login walls.
    Do NOT add www. to URLs that do NOT have them.
    URLs must include the schema: https://example.com is a valid URL while example.com is an invalid URL.

    Args:
        url: The URL to fetch the contents of.
    """
    url_error = _validate_url(url)
    if url_error:
        return f"Error: {url_error}"

    config = _load_config()
    if config.render_mode == "always":
        html, error = await _fetch_rendered_html(url, config)
        if error:
            return error
        return await asyncio.to_thread(_extract_markdown, html, url, config.max_chars)

    html, error = await _fetch_html(url, config)
    if error:
        if config.render_mode == "auto":
            rendered_html, render_error = await _fetch_rendered_html(url, config)
            if rendered_html:
                return await asyncio.to_thread(_extract_markdown, rendered_html, url, config.max_chars)
            if render_error:
                return f"{error}\n{render_error}"
        return error

    markdown = await asyncio.to_thread(_extract_markdown, html, url, config.max_chars)
    if config.render_mode == "auto" and _should_try_render(markdown, config):
        rendered_html, render_error = await _fetch_rendered_html(url, config)
        if rendered_html:
            rendered_markdown = await asyncio.to_thread(_extract_markdown, rendered_html, url, config.max_chars)
            if _meaningful_content_length(rendered_markdown) > _meaningful_content_length(markdown):
                return rendered_markdown
        elif not markdown.strip() and render_error:
            return render_error

    return markdown
