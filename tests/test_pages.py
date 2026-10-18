"""Проверки, которые выполняются на каждой странице из sitemap.xml."""

import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, expect


def open_page(page: Page, page_path: str):
    response = page.goto(page_path, wait_until="load")
    assert response is not None and response.status == 200, f"{page_path}: {response.status}"
    return response


def test_page_opens_without_errors(page: Page, page_path, console_errors):
    open_page(page, page_path)
    page.wait_for_load_state("networkidle")
    assert console_errors == []


def test_page_basic_structure(page: Page, page_path):
    open_page(page, page_path)
    expect(page.locator("html")).to_have_attribute("lang", "ru")
    assert page.title().strip(), "пустой <title>"
    expect(page.locator("h1")).to_have_count(1)
    expect(page.locator("header nav a").first).to_be_visible()


def test_meta_tags_follow_readme_rules(page: Page, page_path):
    """README сайта: og:title и og:description совпадают с title и description,
    canonical и og:url указывают на адрес самой страницы."""
    open_page(page, page_path)

    def meta(selector: str) -> str | None:
        element = page.locator(selector)
        return element.first.get_attribute("content") if element.count() else None

    description = meta('meta[name="description"]')
    assert description, "нет meta description"
    assert 50 <= len(description) <= 250, f"длина description {len(description)}"

    canonical = page.locator('link[rel="canonical"]').get_attribute("href")
    assert urlparse(canonical).path == page_path, f"canonical {canonical} для {page_path}"
    assert meta('meta[property="og:url"]') == canonical
    assert meta('meta[property="og:title"]') == page.title()
    assert meta('meta[property="og:description"]') == description
    assert meta('meta[property="og:image"]'), "нет картинки для превью ссылки"


def test_images_have_alt_and_load(page: Page, page_path):
    open_page(page, page_path)
    # Картинка внутри окна просмотра фото пустая, пока его не открыли, её не проверяем.
    images = page.locator("img:not(dialog img)")
    broken, without_alt = [], []
    for i in range(images.count()):
        img = images.nth(i)
        src = img.get_attribute("src")
        if img.get_attribute("alt") is None:
            without_alt.append(src)
        # Фото могут грузиться лениво (loading="lazy"), поэтому проверяем сам файл запросом.
        response = page.request.get(urljoin(page.url, src))
        if response.status != 200:
            broken.append(f"{src}: {response.status}")
    assert broken == [], "не загружаются картинки"
    assert without_alt == [], "у картинок нет alt"


def test_internal_links_lead_to_existing_pages(page: Page, page_path, base_url):
    open_page(page, page_path)
    hrefs = page.eval_on_selector_all("a[href]", "links => links.map(a => a.getAttribute('href'))")
    site = urlparse(base_url).netloc
    checked, broken = set(), []
    for href in hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(page.url, href)
        parsed = urlparse(url)
        if parsed.netloc != site:
            continue
        if parsed.fragment and parsed.path == urlparse(page.url).path:
            # Якорь на этой же странице: элемент с таким id должен существовать.
            if page.locator(f"[id='{parsed.fragment}']").count() == 0:
                broken.append(f"{href}: нет элемента с id")
            continue
        target = url.split("#")[0]
        if target in checked:
            continue
        checked.add(target)
        status = page.request.get(target).status
        if status != 200:
            broken.append(f"{href}: {status}")
    assert broken == []


def test_assets_use_same_version_everywhere(page: Page, page_path):
    """README сайта: после правки стилей номер ?v= меняют на всех страницах.
    Если забыть одну страницу, на ней браузер покажет старые стили из кэша."""
    open_page(page, page_path)
    assets = page.eval_on_selector_all(
        "link[rel=stylesheet][href*='?v='], script[src*='?v=']",
        "els => els.map(e => e.getAttribute('href') || e.getAttribute('src'))",
    )
    style = [a for a in assets if a.startswith("style.css")]
    assert style, "style.css подключён без номера версии"
    versions = {re.search(r"\?v=(\d+)", a)[1] for a in style}
    assert len(versions) == 1
    # Версию сравниваем с главной страницей.
    page.goto("/")
    main_style = page.locator("link[rel=stylesheet][href^='style.css']").get_attribute("href")
    assert style[0] == main_style, f"{page_path}: {style[0]}, на главной {main_style}"
