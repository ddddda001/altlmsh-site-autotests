"""Общие фикстуры: список страниц из sitemap.xml, браузер и сбор ошибок консоли."""

import os
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pytest

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def load_sitemap(base_url: str) -> list[str]:
    """Пути страниц из sitemap.xml проверяемого сайта, например ["/", "/study.html"]."""
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/sitemap.xml", timeout=30) as response:
        root = ET.fromstring(response.read())
    return [urlparse(loc.text.strip()).path for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)]


def pytest_generate_tests(metafunc):
    # Тесты с аргументом page_path запускаются для каждой страницы из карты сайта:
    # добавили страницу в sitemap.xml — она сразу попала под проверки.
    if "page_path" in metafunc.fixturenames:
        base_url = metafunc.config.getoption("base_url") or metafunc.config.getini("base_url")
        paths = load_sitemap(base_url)
        metafunc.parametrize("page_path", paths, ids=[p.strip("/") or "index" for p in paths])


@pytest.fixture(scope="session")
def sitemap_paths(base_url) -> list[str]:
    return load_sitemap(base_url)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # Если браузер установлен не через `playwright install`, путь к нему можно передать явно.
    path = os.environ.get("CHROMIUM_PATH")
    return {**browser_type_launch_args, **({"executable_path": path} if path else {})}


@pytest.fixture
def console_errors(page):
    """Ошибки JavaScript и не загрузившиеся ресурсы, пойманные за время теста."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"JS: {exc}"))
    page.on(
        "console",
        lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None,
    )
    page.on(
        "response",
        lambda r: errors.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None,
    )
    return errors
