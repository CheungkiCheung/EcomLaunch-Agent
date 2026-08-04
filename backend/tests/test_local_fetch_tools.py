import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from deerflow.community.local_fetch import tools
from deerflow.community.local_fetch.tools import (
    LocalFetchConfig,
    _coerce_bool,
    _coerce_choice,
    _coerce_int,
    _coerce_proxy,
    _meaningful_content_length,
    _should_try_render,
    _validate_url,
    web_fetch_tool,
)


class MockAsyncClient:
    captured_kwargs = {}
    captured_get_kwargs = {}
    response = httpx.Response(
        200,
        text='<html><head><title>Fetched Page</title><meta name="description" content="Short description"></head><body><main><h1>Hello</h1><p>World</p></main></body></html>',
        request=httpx.Request("GET", "https://example.com"),
    )

    def __init__(self, **kwargs):
        type(self).captured_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, **kwargs):
        type(self).captured_get_kwargs = {"url": url, **kwargs}
        return type(self).response


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    app_config = MagicMock()
    app_config.get_tool_config.return_value = None
    monkeypatch.setattr(tools, "get_app_config", lambda: app_config)


@pytest.mark.anyio
async def test_web_fetch_tool_returns_local_markdown(monkeypatch):
    monkeypatch.setattr(tools.httpx, "AsyncClient", MockAsyncClient)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert "# Fetched Page" in result
    assert "Short description" in result
    assert "Hello" in result
    assert "World" in result
    assert not result.startswith("Error:")


@pytest.mark.anyio
async def test_web_fetch_tool_reads_config(monkeypatch):
    app_config = MagicMock()
    tool_config = MagicMock()
    tool_config.model_extra = {
        "timeout": "20",
        "render_timeout": "30",
        "max_chars": "40",
        "min_content_chars": "15",
        "user_agent": "EcomLaunchBot/1.0",
        "proxy": "http://127.0.0.1:7890",
        "trust_env": "false",
        "render_mode": "never",
        "wait_until": "load",
        "render_wait_ms": "500",
        "block_resources": "false",
    }
    app_config.get_tool_config.return_value = tool_config
    monkeypatch.setattr(tools, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools.httpx, "AsyncClient", MockAsyncClient)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert len(result) == 40
    assert MockAsyncClient.captured_kwargs == {
        "follow_redirects": True,
        "trust_env": False,
        "proxy": "http://127.0.0.1:7890",
    }
    assert MockAsyncClient.captured_get_kwargs["timeout"] == 20
    assert MockAsyncClient.captured_get_kwargs["headers"]["User-Agent"] == "EcomLaunchBot/1.0"


@pytest.mark.anyio
async def test_web_fetch_tool_returns_http_error(monkeypatch):
    app_config = MagicMock()
    tool_config = MagicMock()
    tool_config.model_extra = {"render_mode": "never"}
    app_config.get_tool_config.return_value = tool_config
    monkeypatch.setattr(tools, "get_app_config", lambda: app_config)

    MockAsyncClient.response = httpx.Response(
        403,
        text="Forbidden",
        request=httpx.Request("GET", "https://example.com"),
    )
    monkeypatch.setattr(tools.httpx, "AsyncClient", MockAsyncClient)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert result == "Error: Local fetch returned status 403: Forbidden"

    MockAsyncClient.response = httpx.Response(
        200,
        text="<html><head><title>Fetched Page</title></head><body><p>ok</p></body></html>",
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.anyio
async def test_web_fetch_tool_auto_renders_when_static_content_is_thin(monkeypatch):
    MockAsyncClient.response = httpx.Response(
        200,
        text='<html><head><title>App Shell</title></head><body><div id="app-root"></div><script>window.__APP__ = {}</script></body></html>',
        request=httpx.Request("GET", "https://example.com"),
    )
    monkeypatch.setattr(tools.httpx, "AsyncClient", MockAsyncClient)

    async def fake_render(url, config):
        return (
            "<html><head><title>Rendered Page</title></head><body><main><h1>Rendered Product</h1><p>This page has rich rendered ecommerce content after JavaScript hydration.</p></main></body></html>",
            "",
        )

    monkeypatch.setattr(tools, "_fetch_rendered_html", fake_render)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert "# Rendered Page" in result
    assert "Rendered Product" in result
    assert "JavaScript hydration" in result

    MockAsyncClient.response = httpx.Response(
        200,
        text="<html><head><title>Fetched Page</title></head><body><p>ok</p></body></html>",
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.anyio
async def test_web_fetch_tool_always_renders_without_static_fetch(monkeypatch):
    app_config = MagicMock()
    tool_config = MagicMock()
    tool_config.model_extra = {"render_mode": "always"}
    app_config.get_tool_config.return_value = tool_config
    monkeypatch.setattr(tools, "get_app_config", lambda: app_config)

    async def fail_static(*_args, **_kwargs):
        raise AssertionError("static fetch should not run in render_mode=always")

    async def fake_render(url, config):
        return (
            "<html><head><title>Rendered Only</title></head><body><main><p>Rendered content</p></main></body></html>",
            "",
        )

    monkeypatch.setattr(tools, "_fetch_html", fail_static)
    monkeypatch.setattr(tools, "_fetch_rendered_html", fake_render)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert "# Rendered Only" in result
    assert "Rendered content" in result


@pytest.mark.anyio
async def test_web_fetch_tool_preserves_static_result_when_render_fails(monkeypatch):
    MockAsyncClient.response = httpx.Response(
        200,
        text="<html><head><title>Short Page</title></head><body><p>Short</p></body></html>",
        request=httpx.Request("GET", "https://example.com"),
    )
    monkeypatch.setattr(tools.httpx, "AsyncClient", MockAsyncClient)

    async def fake_render(url, config):
        return "", "Error: browser missing"

    monkeypatch.setattr(tools, "_fetch_rendered_html", fake_render)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert "# Short Page" in result
    assert "Short" in result
    assert "browser missing" not in result

    MockAsyncClient.response = httpx.Response(
        200,
        text="<html><head><title>Fetched Page</title></head><body><p>ok</p></body></html>",
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.anyio
async def test_web_fetch_tool_falls_back_to_render_after_static_request_error(monkeypatch):
    async def fake_static(url, config):
        return "", "Error: Local fetch returned status 403: Forbidden"

    async def fake_render(url, config):
        return (
            "<html><head><title>Rendered After Error</title></head><body><main><p>Recovered content</p></main></body></html>",
            "",
        )

    monkeypatch.setattr(tools, "_fetch_html", fake_static)
    monkeypatch.setattr(tools, "_fetch_rendered_html", fake_render)

    result = await web_fetch_tool.ainvoke("https://example.com")

    assert "# Rendered After Error" in result
    assert "Recovered content" in result


@pytest.mark.anyio
async def test_rendered_fetch_closes_page_resources_before_playwright_stops(monkeypatch):
    events: list[str] = []

    class FakePlaywrightError(Exception):
        pass

    class FakePlaywrightTimeoutError(FakePlaywrightError):
        pass

    class FakePage:
        async def goto(self, *_args, **_kwargs):
            events.append("goto")
            return SimpleNamespace(status=200)

        async def content(self):
            return "<html><body><main>Rendered</main></body></html>"

        async def wait_for_timeout(self, _timeout):
            events.append("wait")

        async def unroute_all(self, **_kwargs):
            assert "playwright_exit" not in events
            events.append("unroute")

    class FakeContext:
        async def new_page(self):
            return FakePage()

        async def close(self):
            assert "playwright_exit" not in events
            events.append("context_close")

    class FakeBrowser:
        async def new_context(self, **_kwargs):
            return FakeContext()

        async def close(self):
            assert "playwright_exit" not in events
            events.append("browser_close")

    class FakeChromium:
        async def launch(self, **_kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        async def __aenter__(self):
            events.append("playwright_enter")
            return FakePlaywright()

        async def __aexit__(self, *_args):
            events.append("playwright_exit")

    fake_async_api = SimpleNamespace(
        Error=FakePlaywrightError,
        TimeoutError=FakePlaywrightTimeoutError,
        async_playwright=lambda: FakePlaywrightManager(),
    )
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_async_api)

    html, error = await tools._fetch_rendered_html(
        "https://example.com",
        LocalFetchConfig(block_resources=False, render_wait_ms=0),
    )

    assert error == ""
    assert "Rendered" in html
    assert events[-4:] == ["unroute", "context_close", "browser_close", "playwright_exit"]


@pytest.mark.anyio
async def test_web_fetch_tool_rejects_invalid_url():
    result = await web_fetch_tool.ainvoke("example.com")

    assert result.startswith("Error:")
    assert "http://" in result


def test_validate_url():
    assert _validate_url("https://example.com") is None
    assert _validate_url("http://example.com/path") is None
    assert _validate_url("example.com") is not None
    assert _validate_url("ftp://example.com") is not None


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (True, False, True),
        (False, True, False),
        ("true", False, True),
        ("YES", False, True),
        ("0", True, False),
        ("off", True, False),
        ("maybe", True, True),
        (None, False, False),
    ],
)
def test_coerce_bool(value, default, expected):
    assert _coerce_bool(value, default) is expected


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (10, 1, 10),
        ("20", 1, 20),
        (True, 7, 7),
        ("bad", 7, 7),
        (None, 7, 7),
    ],
)
def test_coerce_int(value, default, expected):
    assert _coerce_int(value, default) == expected


def test_coerce_proxy():
    assert _coerce_proxy(" http://127.0.0.1:7890 ") == "http://127.0.0.1:7890"
    assert _coerce_proxy("   ") is None
    assert _coerce_proxy(None) is None


def test_coerce_choice():
    assert _coerce_choice("always", "auto", {"auto", "always", "never"}) == "always"
    assert _coerce_choice(" LOAD ", "domcontentloaded", {"load", "domcontentloaded"}) == "load"
    assert _coerce_choice("bad", "auto", {"auto", "always", "never"}) == "auto"
    assert _coerce_choice(None, "auto", {"auto", "always", "never"}) == "auto"


def test_should_try_render():
    config = LocalFetchConfig(min_content_chars=20)

    assert _should_try_render("# App\n\nPlease enable JavaScript to continue.", config)
    assert _should_try_render("# Thin\n\nShort", config)
    assert not _should_try_render(
        "# Rich\n\nThis static page already has enough meaningful content for extraction.",
        config,
    )
    assert not _should_try_render("# Thin\n\nShort", LocalFetchConfig(render_mode="never", min_content_chars=20))


def test_meaningful_content_length_ignores_metadata_quote_lines():
    assert _meaningful_content_length("# Title\n\n> metadata description\n\nVisible body") < len("# Title\n\n> metadata description\n\nVisible body")


def test_extract_markdown_falls_back_to_body_text(monkeypatch):
    class EmptyArticle:
        title = "Untitled"

        def to_markdown(self):
            return "# Untitled\n\nNo content could be extracted from this page"

    class EmptyExtractor:
        def extract_article(self, html):
            return EmptyArticle()

    monkeypatch.setattr(tools, "readability_extractor", EmptyExtractor())

    result = tools._extract_markdown(
        "<html><head><title>Fallback</title></head><body><main><p>Visible text</p></main></body></html>",
        "https://example.com",
        4096,
    )

    assert result == "# Fallback\n\nVisible text"
