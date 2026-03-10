# --------------------------------------------------
# external
# --------------------------------------------------
import logging
import requests
from enum import Enum
from bs4 import BeautifulSoup
from typing import List, Optional
from dataclasses import dataclass
from bs4.element import NavigableString, Tag
from playwright.sync_api import Route, sync_playwright


class ZodiacSign(Enum):
    ARIES = "Aries"
    TAURUS = "Taurus"
    GEMINI = "Gemini"
    CANCER = "Cancer"
    LEO = "Leo"
    VIRGO = "Virgo"
    LIBRA = "Libra"
    SCORPIO = "Scorpio"
    SAGITTARIUS = "Sagittarius"
    CAPRICORN = "Capricorn"
    AQUARIUS = "Aquarius"
    PISCES = "Pisces"

    def __str__(self):
        return self.value


@dataclass
class HoroscopeCriterion:
    action: str  # "find" | "find_all" | "find_first_text"
    tag: Optional[str] = None
    class_name: Optional[str] = None
    text_prefixes: Optional[List[str]] = None


# --------------------------------------------------
# fallback: navigate the tree to the horoscope paragraph via its
# unique ancestor chain (app-horoscope-table-list > div.zodiac-table
# > div.strapi_bg > div.content-page), then take the first <p>.
# --------------------------------------------------
HOROSCOPE_CRITERIA_TREE: List[HoroscopeCriterion] = [
    HoroscopeCriterion(action="find", tag="app-horoscope-table-list"),
    HoroscopeCriterion(action="find", tag="div", class_name="zodiac-table"),
    HoroscopeCriterion(action="find", tag="div", class_name="strapi_bg"),
    HoroscopeCriterion(action="find", tag="div", class_name="content-page"),
    HoroscopeCriterion(action="find_first_text", tag="p"),
]
# --------------------------------------------------
# primary: search all content-page divs for a paragraph starting with "Dear "
# --------------------------------------------------
HOROSCOPE_CRITERIA_DEAR: List[HoroscopeCriterion] = [
    HoroscopeCriterion(action="find", tag="div", class_name="content-page"),
    HoroscopeCriterion(action="find_all", tag="p"),
    HoroscopeCriterion(action="find_first_text", text_prefixes=["Dear "]),
]
HOROSCOPE_CRITERIA: List[List[HoroscopeCriterion]] = [
    HOROSCOPE_CRITERIA_DEAR,
    HOROSCOPE_CRITERIA_TREE,
]


def _get_and_render(url: str, selector: str = "") -> BeautifulSoup:
    # --------------------------------------------------
    # naively makes request, without rendering
    # --------------------------------------------------
    # response = requests.get(url, timeout=10)
    # response.raise_for_status()
    # soup = BeautifulSoup(response.content, 'html.parser')

    # --------------------------------------------------
    # makes request, with rendering
    # --------------------------------------------------
    with sync_playwright() as p:
        # --------------------------------------------------
        # open browser and page
        # --------------------------------------------------
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # --------------------------------------------------
        # block junk
        # --------------------------------------------------
        def block(route: Route):
            if any(
                ext in route.request.url
                for ext in [".png", ".jpg", ".svg", ".gif", ".css"]
            ):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", block)
        # --------------------------------------------------
        # goto url, wait for selector, get content, close browser
        # --------------------------------------------------
        page.goto(url)
        page.wait_for_selector(selector)
        html = page.content()
        browser.close()
    # --------------------------------------------------
    # parse and return soup
    # --------------------------------------------------
    return BeautifulSoup(html, "html.parser")


def _string_to_birthday(birthday: str) -> tuple[int, int]:
    """
    Converts a birthday string in "YYYY-MM-DD" or "MM-DD" format to a (day, month) tuple.

    Args:
        birthday: The birthday string to convert

    Returns:
        A tuple containing the day and month as integers
    """
    parts = birthday.split("-")
    if len(parts) == 3:
        # --------------------------------------------------
        # format: YYYY-MM-DD
        # --------------------------------------------------
        _, month_str, day_str = parts
    elif len(parts) == 2:
        # --------------------------------------------------
        # format: MM-DD
        # --------------------------------------------------
        month_str, day_str = parts
    else:
        raise ValueError("Invalid birthday format. Use 'YYYY-MM-DD' or 'MM-DD'.")
    return int(day_str), int(month_str)


def _birthday_to_zodiac_sign(day: int, month: int) -> ZodiacSign:
    """Returns Zodiac Sign, given a birthday.

    Args:
        day (int): Day of birthday
        month (int): Month of birthday

    Raises:
        ValueError: If invalid month/day (out of range)

    Returns:
        str: Returns Zodiac sign as a string.
    """
    # --------------------------------------------------
    # month and day validation
    # --------------------------------------------------
    if not 1 <= month <= 12:
        raise ValueError("Invalid month for zodiac sign")
    days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # allow Feb 29
    if not 1 <= day <= days_in_month[month - 1]:
        raise ValueError("Invalid day for zodiac sign")
    # --------------------------------------------------
    # determine zodiac by date ranges (inclusive)
    # --------------------------------------------------
    if (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return ZodiacSign.CAPRICORN
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return ZodiacSign.AQUARIUS
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return ZodiacSign.PISCES
    elif (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return ZodiacSign.ARIES
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return ZodiacSign.TAURUS
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return ZodiacSign.GEMINI
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return ZodiacSign.CANCER
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return ZodiacSign.LEO
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return ZodiacSign.VIRGO
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return ZodiacSign.LIBRA
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return ZodiacSign.SCORPIO
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return ZodiacSign.SAGITTARIUS
    else:
        raise ValueError(
            "Invalid date for zodiac sign"
        )  # should never reach here due to validation, but just in case


def _apply_criteria(
    soup: BeautifulSoup, criteria: List[HoroscopeCriterion]
) -> Optional[str]:
    """Applies a `HoroscopeCriterion` to a soup, in attempt to extract
    the horoscope text

    Args:
        soup: The BeautifulSoup
        criteria: A list of HoroscopeCriterion

    Returns:
        An optional found text, None if not found.
    """
    current = soup
    for criterion in criteria:
        # --------------------------------------------------
        # simple find
        # --------------------------------------------------
        if criterion.action == "find":
            current = current.find(criterion.tag, class_=criterion.class_name)
            if not current:
                return None
        # --------------------------------------------------
        # simple find_all
        # --------------------------------------------------
        elif criterion.action == "find_all":
            current = current.find_all(criterion.tag)
            if not current:
                return None
        # --------------------------------------------------
        # find first instance, more complicated but faster
        # --------------------------------------------------
        elif criterion.action == "find_first_text":
            elements = current if isinstance(current, list) else [current]
            if criterion.tag:
                expanded = []
                for el in elements:
                    if el.name == criterion.tag:
                        expanded.append(el)
                    else:
                        expanded.extend(el.find_all(criterion.tag))
                elements = expanded
            for element in elements:
                # --------------------------------------------------
                # init text, search for in element
                # --------------------------------------------------
                text = None
                for child in element.contents:
                    if isinstance(child, NavigableString):
                        _text = child.strip()
                        if _text:
                            text = _text
                            break
                    elif isinstance(child, Tag):
                        _text = child.get_text(strip=True)
                        if _text:
                            text = _text
                            break
                # --------------------------------------------------
                # if not found, continue to next element
                # --------------------------------------------------
                if not text:
                    continue
                if criterion.text_prefixes:
                    if any(text.startswith(p) for p in criterion.text_prefixes):
                        return text
                else:
                    return text
            return None
    return None


def _horoscope_request(sign: ZodiacSign) -> Optional[tuple[str, str]]:
    """
    Fetch horoscope content for a zodiac sign. Uses `astroyogi.com`.

    Args:
        url: The URL to fetch the horoscope from

    Returns:
        Optional[tuple[str, str]]: The extracted horoscope text and URL, or None if not found
    """
    url = f"https://www.astroyogi.com/horoscopes/daily/{sign.value.lower()}-free-horoscope.aspx"
    try:
        # --------------------------------------------------
        # make request
        # --------------------------------------------------
        selector = "div.content-page"
        soup = _get_and_render(
            url, selector
        )  # render the page with playwright to get dynamic content
        # --------------------------------------------------
        # try each criteria list in order, use the first match
        # --------------------------------------------------
        first_child_text = None
        for criteria_list in HOROSCOPE_CRITERIA:
            result = _apply_criteria(soup, criteria_list)
            if result is not None:
                first_child_text = result
                break
        # --------------------------------------------------
        # return None if not found
        # --------------------------------------------------
        if not first_child_text:
            logging.error(
                "Could not find horoscope paragraph matching any criteria in the content div"
            )
            return None
        # --------------------------------------------------
        # find and replace "Astroyogi a" with "a"
        # --------------------------------------------------
        first_child_text = first_child_text.replace("Astroyogi a", "a")
        # --------------------------------------------------
        # ensure all sentence beginnings start with a capital
        # letters (some of them are lowercase in the source)
        # --------------------------------------------------
        sentences = first_child_text.split(". ")
        sentences = [s[:1].upper() + s[1:] if s else s for s in sentences]
        first_child_text = ". ".join(sentences)
        # --------------------------------------------------
        # return the horoscope text and URL
        # --------------------------------------------------
        return first_child_text, url

    # --------------------------------------------------
    # catch and log any exceptions that occur during the request or parsing
    # --------------------------------------------------
    except requests.RequestException:
        logging.exception("Error fetching horoscope URL")
        return None
    except Exception:
        logging.exception("Error parsing horoscope content")
        return None


def get_horoscope_for_birthday(birthday: str) -> Optional[tuple[str, str]]:
    """
    Get the horoscope text for a given birthday.

    Args:
        birthday: The birthday string in "YYYY-MM-DD" or "MM-DD" format

    Returns:
        Optional[tuple[str, str]]: The horoscope text and link, or None if not found
    """
    # --------------------------------------------------
    # parse birthday, get zodiac sign
    # --------------------------------------------------
    try:
        day, month = _string_to_birthday(birthday)
        zodiac_sign = _birthday_to_zodiac_sign(day, month)
    except ValueError:
        logging.exception("Error processing birthday input: %s", birthday)
        return None
    # --------------------------------------------------
    # fetch and return horoscope
    # --------------------------------------------------
    try:
        return _horoscope_request(zodiac_sign)
    except ValueError:
        logging.exception("Error processing horoscope request")
        return None


if __name__ == "__main__":
    for sign in ZodiacSign:
        result = _horoscope_request(sign)
        if result:
            text, _ = result
            print(f"OK   {sign.value:12s} {text[:80]}...")
        else:
            print(f"FAILED {sign.value}")
