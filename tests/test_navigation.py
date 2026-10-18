"""Меню, карта сайта и мобильная версия."""

from urllib.parse import urljoin, urlparse

import pytest
from playwright.sync_api import Page, expect


def menu_paths(page: Page) -> set[str]:
    hrefs = page.eval_on_selector_all(
        "header nav a[href]", "links => links.map(a => a.getAttribute('href'))"
    )
    return {urlparse(urljoin(page.url, h)).path for h in hrefs}


def test_menu_is_the_same_on_every_page(page: Page, sitemap_paths):
    page.goto("/")
    reference = menu_paths(page)
    different = {}
    for path in sitemap_paths:
        page.goto(path)
        menu = menu_paths(page)
        if menu != reference:
            different[path] = {"нет": sorted(reference - menu), "лишние": sorted(menu - reference)}
    assert different == {}


def test_every_menu_page_is_in_sitemap(page: Page, sitemap_paths):
    """README сайта: новую страницу добавляют и в меню, и в sitemap.xml."""
    page.goto("/")
    normalized = {p if p != "/index.html" else "/" for p in menu_paths(page)}
    assert normalized - set(sitemap_paths) == set()


def test_robots_txt_points_to_sitemap(page: Page):
    response = page.request.get("/robots.txt")
    assert response.status == 200
    assert "sitemap.xml" in response.text().lower()


@pytest.mark.mobile
def test_mobile_menu_opens_and_closes(page: Page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto("/")
    toggle = page.locator(".menu-toggle")
    nav = page.locator("#site-nav")

    expect(toggle).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(nav).to_be_hidden()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(toggle).to_have_text("Закрыть")
    expect(nav).to_be_visible()
    expect(nav.locator("a").first).to_be_visible()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_text("Меню")
    expect(nav).to_be_hidden()


@pytest.mark.mobile
def test_mobile_menu_toggle_hidden_on_desktop(page: Page):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("/")
    expect(page.locator(".menu-toggle")).to_be_hidden()
    expect(page.locator("#site-nav")).to_be_visible()


@pytest.mark.mobile
@pytest.mark.parametrize("width", [320, 375, 768])  # 320 — регрессия BUG-001
def test_no_horizontal_scroll_on_phones(page: Page, sitemap_paths, width):
    page.set_viewport_size({"width": width, "height": 800})
    overflow = {}
    for path in sitemap_paths:
        page.goto(path)
        extra = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if extra > 0:
            overflow[path] = extra
    assert overflow == {}, f"страница шире экрана {width}px на столько пикселей"
