import re
import regex

URL_PART_BEFORE_ID = '2edit_ajax'

DEFAULT_PARSER = 'lxml'
BASE_URL = "https://koshelek.org"
RE_CURRENCY = regex.compile(r"(?P<currency>[\p{Alpha}$€]+)(?P<value>[\d ]+(\.|\,)\d{2})", regex.UNICODE)
RE_AJAX_ARGS_URL = re.compile(r'showAjaxWindow\(\"(?P<ajax_url>.+?)\"')

HTTP_OK = 200


COST_NAME, INCOME_NAME = 'cost', 'income'
PRICE_EDITOR_ELEMENT_INDEX = 3
