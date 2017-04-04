import re
import datetime
import logging
import threading

from calendar import monthrange
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Union
from queue import Queue, Empty

import regex
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning


from bs4 import BeautifulSoup

from exporters import CSVExporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('koshelek.parser')
logging\
    .getLogger('requests.packages.urllib3.connectionpool')\
    .setLevel(logging.WARNING)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


URL_PART_BEFORE_ID = '2edit_ajax'

DEFAULT_PARSER = 'lxml'
BASE_URL = "https://koshelek.org"
RE_CURRENCY = regex.compile(r"(?P<currency>[\p{Alpha}$€]+)(?P<value>[\d ]+(\.|\,)\d{2})", regex.UNICODE)
RE_AJAX_ARGS_URL = re.compile(r'showAjaxWindow\(\"(?P<ajax_url>.+?)\"')

HTTP_OK = 200


COST_NAME, INCOME_NAME = 'cost', 'income'
PRICE_EDITOR_ELEMENT_INDEX = 3


def split_currency(sum_str: str) -> Tuple[str, str]:
    sum_str = sum_str.replace('\xa0', ' ')
    match = RE_CURRENCY.match(sum_str)
    if not match:
        raise ValueError("Incorrect currency string: {}".format(sum_str))
    cur = match.groupdict()['currency']
    value = match.groupdict()['value']
    value = value.replace(',', '.').replace(' ', '')
    return cur, value


Cost = namedtuple("Cost",
                  ["id", "title", "description", "category",
                   "budget", "currency", "value", "account", "date"])
Income = namedtuple("Income",
                    ["id", "title", "description", "category",
                     "budget", "currency", "value", "account", "date"])
Exchange = namedtuple("Exchange",
                      ["id", "title", "description", "budget", "currency",
                       "value", "account_from", "account_to", "date"])
Account = namedtuple("Account",
                     ["title", "description", "default_currency", "remnants"])


Operations = List[Union[Income, Cost]]


def _extract_td_elements(soup: BeautifulSoup) -> str:
    return soup.find_all("td")


def _extract_ajax_url(soup: BeautifulSoup) -> str:
    td_elements = _extract_td_elements(soup)
    element_with_ajax = td_elements[PRICE_EDITOR_ELEMENT_INDEX]
    url_ = element_with_ajax.a['onclick']
    return RE_AJAX_ARGS_URL.findall(url_)[0]


def _get_operation_from_ajax_url(ajax_url):
    """
    Example

    >>> c._get_operation_from_ajax_url('/income/2edit_ajax128')
    >>> 'income'
    """
    return ajax_url.split('/')[1]


class IncomeParseStrategy(object):

    @staticmethod
    def parse(session, block):
        td_els = _extract_td_elements(block)
        ajax_url = _extract_ajax_url(block)
        # FIXME: moved to base class
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
        title = td_els[0].a.text
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = split_currency(money)
        account = td_els[4].a.text
        date = td_els[5].a.text
        return Income(id=_id, title=title, description="", category=category,
                      budget=budget, currency=cur, value=value,
                      account=account, date=date)

    @staticmethod
    def _extract_id_from_url(ajax_url):
        indx = ajax_url.find(URL_PART_BEFORE_ID) + len(URL_PART_BEFORE_ID)
        ajax_url = ajax_url[indx:]
        return_url_pos = ajax_url.find('?return_url')
        if return_url_pos:
            ajax_url = ajax_url[:return_url_pos]
        return ajax_url


class CostParseStrategy(object):

    @staticmethod
    def parse(session, block):
        td_els = _extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = _extract_ajax_url(block)
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = split_currency(money)
        account = td_els[4].a.text
        date = td_els[5].a.text
        return Cost(id=_id, title=title, description="", category=category,
                    budget=budget, currency=cur, value=value,
                    account=account, date=date)

    @staticmethod
    def _extract_id_from_url(ajax_url):
        indx = ajax_url.find(URL_PART_BEFORE_ID) + len(URL_PART_BEFORE_ID)
        return ajax_url[indx:]


class ExchangeParseStrategy(object):

    @classmethod
    def parse(cls, session, block):
        td_els = _extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = _extract_ajax_url(block)
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
        account_from, account_to = cls._parse_editorial_form(session, ajax_url)
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = split_currency(money)
        date = td_els[5].a.text
        # FIXME: fix description
        return Exchange(id=_id, title=title,
                        budget=budget, currency=cur, description='',
                        account_from=account_from, account_to=account_to,
                        value=value,
                        date=date)

    @staticmethod
    def _parse_editorial_form(session, ajax_url):
        response = session.get(BASE_URL + ajax_url, verify=False)
        soup = BeautifulSoup(response.text, DEFAULT_PARSER)

        account_from = soup\
            .find('select', id='accountFrom')\
            .find('option', selected='selected')\
            .text

        account_to = soup\
            .find('select', id='accountTo')\
            .find('option', selected='selected')\
            .text

        return account_to, account_from


class BlockParser(object):

    OPERATION_MAP = {
        'income': IncomeParseStrategy,
        'costs': CostParseStrategy,
        'transfer': ExchangeParseStrategy,
    }

    def __init__(self, session: requests.Session):
        self.session = session

    def parse_block(self, block: BeautifulSoup):
        url = _extract_ajax_url(block)
        operation_type = _get_operation_from_ajax_url(url)
        parse_strategy = self.OPERATION_MAP[operation_type]
        return parse_strategy.parse(self.session, block)


class IncorrectCredentials(ValueError):
    pass


class KoshelekParser(object):

    SESSION_COOKIE_NAME = "JSESSIONID"

    URLS = {
        "login": BASE_URL + "/login",
        "income": BASE_URL + "/income",
        "cost": BASE_URL + "/costs",
    }

    DATA_CLASS = "data_line"

    def __init__(self,
                 username: str="",
                 password: str="",
                 exporter=None,
                 threads=2) -> None:
        if not (username and password):
            msg = "Password or username is empty."
            raise IncorrectCredentials(msg)
        self.username = username
        self.password = password
        self._logger = logging.getLogger("koshelek.parser")
        self._exporter = exporter or CSVExporter()
        self._session = self._initialize_session()
        self._block_parser = BlockParser(self._session)
        self._number_of_threads = threads

        self.producer_pool = ThreadPoolExecutor(max_workers=self._number_of_threads,
                                                thread_name_prefix='producer-')
        self.consumer_pool = ThreadPoolExecutor(max_workers=self._number_of_threads,
                                                thread_name_prefix='consumer-')
        self._authorise_session()

    def _extract_operation_blocks_from_page(self,
                                            page_text: str) -> List[BeautifulSoup]:
        soup = BeautifulSoup(page_text, DEFAULT_PARSER)
        return soup.find_all("tr", self.DATA_CLASS)

    def get_operations_content(self, year="", month="", operation=COST_NAME):
        if month and not year:
            year = datetime.datetime.now().year
        if not month and year:
            month = datetime.datetime.now().month
        if not (year or month):
            year = datetime.datetime.now().year
            month = datetime.datetime.now().month
        logger.info("Getting {op} for {month}.{year}"
                    .format(op=operation, month=month, year=year))
        operation_type_url = self.URLS.get(operation, COST_NAME)
        date_filter = self.get_date_filter_dict_for_month(month, year)
        return self.get_url_content(operation_type_url,
                                    param_dict=date_filter)

    def _get_month_and_year_diff(self, cur_year, cur_month, month_count):
        month_diff = cur_month - month_count
        year = cur_year
        month = month_diff
        if month_diff <= 0:
            month = 12 - abs(month_diff) % 12
            year = cur_year - abs(month_diff) // 12 - 1
        return month, year

    def get_date_filter_dict_for_month(self,
                                       month_num: int,
                                       year: int) -> dict:
        """Generate filter date parameters for URL.
        Assume that you want to get statistics for the march of 2015:
        pass 3, 2015 as params and you will get dict {'filtrDateStart': '01.03.2015', 'filtrDateEnd': '31.03.2105'}
        that cand be passed as param for the date request
        """
        # TODO: cover with tests
        month = int(month_num)
        year = int(year)
        __, days_count = monthrange(year, month)
        return {"filtrDateStart": "01.{:02d}.{}".format(month, year),
                "filtrDateEnd": "{}.{:02d}.{}".format(days_count, month, year)}

    def get_operations_for_months(self,
                                  now: datetime.datetime=None,
                                  months: int=1) -> Operations:
        """
        Get all costs or incomes within the range of
        given number of months from the current day.
        """
        now = now or datetime.datetime.now()

        blocks = Queue()
        operations = Queue()
        blocks_obtained = threading.Event()

        producer = threading.Thread(target=self._get_blocks_for_months,
                                    args=(now, months, blocks, blocks_obtained))
        consumer = threading.Thread(target=self._parse_blocks,
                                    args=(blocks, operations, blocks_obtained))

        producer.start()
        consumer.start()

        producer.join()
        consumer.join()

        return self._extract_operations_from_queue(operations)

    def _extract_operations_from_queue(self, operations):
        costs = []
        incomes = []
        exchanges = []
        while not operations.empty():
            op = operations.get()
            if isinstance(op, Income):
                incomes.append(op)
            elif isinstance(op, Cost):
                costs.append(op)
            elif isinstance(op, Exchange):
                exchanges.append(op)
            else:
                logger.warn("Unknown operation type: %s (%s)",
                            op, type(op))
        return costs, incomes, exchanges

    def _get_blocks_for_months(self, now, months, queue,
                               blocks_obtained: threading.Event):
        # TODO: threads should better be used while processing
        # specific blocks
        futures_ = (self.producer_pool.submit(self.get_operations_content, year, month, operation)
                    for (month, year) in self.__month_year_iterator(now, months)
                    for operation in (COST_NAME, INCOME_NAME))
        self.producer_pool.submit(futures_)
        for future in as_completed(futures_):
            try:
                costs_page = future.result()
                for block in self._extract_operation_blocks_from_page(costs_page):
                    queue.put(block)
            except Exception as e:
                logger.exception("Unknown error occured while parsing the page.")
        logger.info("Block obtaining finished.")
        blocks_obtained.set()

    def _parse_blocks(self,
                      blocks: Queue,
                      operations: Queue,
                      blocks_obtained: threading.Event):
        future_results = []
        while True:
            if blocks_obtained.is_set() and blocks.empty():
                break
            try:
                if not blocks.empty():
                    block_to_parse = blocks.get(timeout=10)
                    future = self.consumer_pool.submit(self._block_parser.parse_block,
                                                       block_to_parse)
                    future_results.append(future)
            except Empty:
                break
        for future in as_completed(future_results):
            try:
                operations.put(future.result())
            except Exception as e:
                logger.exception("Error parsing the operation.")
        logger.info("Operations parsing completed.")

    def __month_year_iterator(self, now: datetime.datetime=None,
                              months: int=1):
        cur_month = now.month
        cur_year = now.year

        for diff_month_i in range(0, months):
            month, year = self._get_month_and_year_diff(cur_year,
                                                        cur_month,
                                                        diff_month_i)
            yield month, year

    @staticmethod
    def _initialize_session() -> requests.Session:
        session = requests.Session()
        return session

    def _authorise_session(self) -> requests.Session:
        """
        Perform login request with provided
        credentials and save the authorisation
        cookie into the local session.
        """
        self._session.get(BASE_URL, verify=False)
        payload = {
            'user.login': self.username,
            'user.password': self.password,
            'saveUser': True
        }
        self._session.post(self.URLS["login"], data=payload)
        return self._session

    def export_to_file(self,
                       operations: Operations,
                       filename: str,
                       **kwargs):
        """
        Dumps specified incomes or costs to file
        with the help of the given exporter.
        """
        if not self._exporter:
            raise ValueError("No exporter set up to be used.")
        self._exporter.export_to_file(operations, filename, **kwargs)

    def get_url_content(self, url: str, param_dict: dict=None) -> str:
        """
        Reads URL content
        """
        param_dict = param_dict or {}
        r = self._session.get(url, params=param_dict, verify=False)
        assert r.status_code == HTTP_OK
        return r.text
