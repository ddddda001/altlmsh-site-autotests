"""Интерактивные части сайта: фильтры на странице «Люди», история смен, просмотр фото."""

import re

from playwright.sync_api import Page, expect

STATUS = re.compile(r"показано (\d+) из (\d+)")


def shown_count(page: Page) -> tuple[int, int]:
    match = STATUS.search(page.locator(".people-status").inner_text())
    assert match, page.locator(".people-status").inner_text()
    return int(match[1]), int(match[2])


def visible_cards(page: Page) -> int:
    return page.locator(".people-list > li:not([hidden])").count()


def chip(page: Page, key: str, value: str):
    return page.locator(f".chip[data-key='{key}'][data-value='{value}']")


# --- «Люди» --------------------------------------------------------------------------------------


def test_people_without_filters_shows_everyone(page: Page):
    page.goto("/people.html")
    shown, total = shown_count(page)
    assert shown == total == page.locator(".people-list > li").count() > 0
    expect(chip(page, "year", "")).to_have_attribute("aria-pressed", "true")
    expect(chip(page, "dept", "")).to_have_attribute("aria-pressed", "true")


def test_people_year_filter(page: Page):
    page.goto("/people.html")
    year_chip = page.locator(".chip[data-key='year']:not([data-value=''])").first
    year = year_chip.get_attribute("data-value")
    year_chip.click()

    shown, total = shown_count(page)
    assert 0 < shown <= total
    assert visible_cards(page) == shown
    expect(year_chip).to_have_attribute("aria-pressed", "true")
    expect(page).to_have_url(re.compile(rf"year={year}"))
    for card in page.locator(".people-list > li:not([hidden]) .person-years").all_inner_texts():
        assert year in card or "–" in card, f"{card} не содержит {year}"


def test_people_filter_from_url(page: Page):
    page.goto("/people.html?dept=Физмат")
    expect(chip(page, "dept", "Физмат")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".people-status")).to_contain_text("Физмат")
    for dept in page.locator(".people-list > li:not([hidden]) .person-dept").all_inner_texts():
        assert "Физмат" in dept


def test_people_reset_with_all(page: Page):
    page.goto("/people.html?dept=Физмат")
    filtered, total = shown_count(page)
    chip(page, "dept", "").click()
    assert shown_count(page) == (total, total)
    assert "dept=" not in page.url
    assert filtered < total


def test_people_no_shift_year_shows_message(page: Page):
    # В 2020 году смены не было, людей с таким годом быть не должно.
    page.goto("/people.html?year=2020")
    expect(page.locator(".people-status")).to_have_text(
        "Никого не нашли — попробуй другой год или кафедру"
    )
    assert visible_cards(page) == 0


def test_people_unknown_filter_value(page: Page):
    """Значение из адреса, которого нет среди кнопок, например старая или испорченная ссылка.
    Регрессия BUG-002."""
    page.goto("/people.html?year=abc")
    expect(page.locator(".people-status")).to_contain_text("Никого не нашли")
    # Пользователь должен видеть, какой фильтр сейчас действует, чтобы сбросить его.
    expect(page.locator(".chip[aria-pressed='true']")).to_have_count(2)


# --- «История» -----------------------------------------------------------------------------------


def test_history_year_links_match_shifts(page: Page):
    page.goto("/history.html")
    shifts = page.locator("article.shift")
    links = page.locator(".year-nav a")
    expect(links).to_have_count(shifts.count())
    for i in range(links.count()):
        target = links.nth(i).get_attribute("href").lstrip("#")
        expect(page.locator(f"#{target}")).to_have_count(1)


def test_history_year_link_scrolls_to_shift(page: Page):
    page.goto("/history.html")
    link = page.locator(".year-nav a").last
    target = link.get_attribute("href")
    link.click()
    expect(page).to_have_url(re.compile(f"{target}$"))
    expect(page.locator(target)).to_be_in_viewport()


# --- Просмотр фото -------------------------------------------------------------------------------


def test_photo_opens_and_closes_by_click(page: Page):
    page.goto("/history.html")
    photo = page.locator(".photos img").first
    photo.scroll_into_view_if_needed()
    photo.click()
    viewer = page.locator("dialog.photo-viewer")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute("src", photo.evaluate("img => img.src"))
    viewer.click()
    expect(viewer).to_be_hidden()


def test_photo_keyboard_access(page: Page):
    page.goto("/history.html")
    photo = page.locator(".photos img").first
    photo.focus()
    page.keyboard.press("Enter")
    viewer = page.locator("dialog.photo-viewer")
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    # После закрытия фокус возвращается на фото, чтобы можно было листать дальше с клавиатуры.
    expect(photo).to_be_focused()


def test_photo_has_button_semantics(page: Page):
    """Фото открывается по нажатию, значит экранная читалка должна объявлять его как кнопку.
    Регрессия BUG-003."""
    page.goto("/history.html")
    photo = page.locator(".photos img").first
    assert photo.get_attribute("role") == "button" or photo.evaluate(
        "img => img.closest('button, a') !== null"
    )
