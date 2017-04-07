from typing import Tuple

from bs4 import BeautifulSoup

import constants


def _extract_td_elements(soup: BeautifulSoup) -> str:
    return soup.find_all("td")


def _extract_ajax_url(soup: BeautifulSoup) -> str:
    td_elements = _extract_td_elements(soup)
    element_with_ajax = td_elements[constants.PRICE_EDITOR_ELEMENT_INDEX]
    url_ = element_with_ajax.a['onclick']
    return constants.RE_AJAX_ARGS_URL.findall(url_)[0]


def _get_operation_from_ajax_url(ajax_url):
    """
    Example

    >>> c._get_operation_from_ajax_url('/income/2edit_ajax128')
    >>> 'income'
    """
    return ajax_url.split('/')[1]


def split_currency(sum_str: str) -> Tuple[str, str]:
    sum_str = sum_str.replace('\xa0', ' ')
    match = constants.RE_CURRENCY.match(sum_str)
    if not match:
        raise ValueError("Incorrect currency string: {}".format(sum_str))
    cur = match.groupdict()['currency']
    value = match.groupdict()['value']
    value = value.replace(',', '.').replace(' ', '')
    return cur, value
