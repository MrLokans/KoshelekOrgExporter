import datetime
import logging
import threading

from calendar import monthrange
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Union
from queue import Queue, Empty

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup

import constants
from exporters import CSVExporter
import operations as ops
import parsing_strategies as strategies
import utils


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('koshelek.parser')
logging\
    .getLogger('requests.packages.urllib3.connectionpool')\
    .setLevel(logging.WARNING)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class BlockParser(object):

    OPERATION_MAP = {
        'income': strategies.IncomeParseStrategy,
        'costs': strategies.CostParseStrategy,
        'transfer': strategies.ExchangeParseStrategy,
    }

    def __init__(self, session: requests.Session):
        self.session = session

    def parse_block(self, block: BeautifulSoup):
        url = utils._extract_ajax_url(block)
        operation_type = utils._get_operation_from_ajax_url(url)
        parse_strategy = self.OPERATION_MAP[operation_type]
        return parse_strategy.parse(self.session, block)


class IncorrectCredentials(ValueError):
    pass


class KoshelekParser(object):

    SESSION_COOKIE_NAME = "JSESSIONID"

    URLS = {
        "login": constants.BASE_URL + "/login",
        "income": constants.BASE_URL + "/income",
        "cost": constants.BASE_URL + "/costs",
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
        soup = BeautifulSoup(page_text, constants.DEFAULT_PARSER)
        return soup.find_all("tr", self.DATA_CLASS)

    def get_operations_content(self, year="", month="", operation=constants.COST_NAME):
        if month and not year:
            year = datetime.datetime.now().year
        if not month and year:
            month = datetime.datetime.now().month
        if not (year or month):
            year = datetime.datetime.now().year
            month = datetime.datetime.now().month
        logger.info("Getting {op} for {month}.{year}"
                    .format(op=operation, month=month, year=year))
        operation_type_url = self.URLS.get(operation, constants.COST_NAME)
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
                                  months: int=1) -> ops.Operations:
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
        costs, incomes, exchanges = [], [], []
        while not operations.empty():
            op = operations.get()
            if isinstance(op, ops.Income):
                incomes.append(op)
            elif isinstance(op, ops.Cost):
                costs.append(op)
            elif isinstance(op, ops.Exchange):
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
                    for operation in (constants.COST_NAME, constants.INCOME_NAME))
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
        return requests.Session()

    def _authorise_session(self) -> requests.Session:
        """
        Perform login request with provided
        credentials and save the authorisation
        cookie into the local session.
        """
        self._session.get(constants.BASE_URL, verify=False)
        payload = {
            'user.login': self.username,
            'user.password': self.password,
            'saveUser': True
        }
        self._session.post(self.URLS["login"], data=payload)
        return self._session

    def export_to_file(self,
                       operations: ops.Operations,
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
        assert r.status_code == constants.HTTP_OK
        return r.text
