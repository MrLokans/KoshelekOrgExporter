import datetime
import logging
from calendar import monthrange
from collections import namedtuple
from functools import partial
from itertools import filterfalse
from typing import List, Tuple, Union

import regex
import requests

from bs4 import BeautifulSoup

from exporters import CSVExporter

logging.basicConfig(level=logging.INFO)

RE_CURRENCY = regex.compile(r"(?P<currency>[\p{Alpha}$€]+)(?P<value>[\d ]+(\.|\,)\d{2})", regex.UNICODE)
HTTP_OK = 200


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
                  ["title", "description", "category",
                   "budget", "currency", "value", "account", "date"])
Income = namedtuple("Income",
                    ["title", "description", "category",
                     "budget", "currency", "value", "account", "date"])
Account = namedtuple("Account",
                     ["title", "description", "default_currency", "remnants"])


Operations = List[Union[Income, Cost]]


class IncorrectCredentials(ValueError):
    pass


class KoshelekParser(object):

    BASE_URL = "https://koshelek.org"
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
                 exporter=None) -> None:
        if not (username and password):
            msg = "Password or username is empty."
            raise IncorrectCredentials(msg)
        self.username = username
        self.password = password
        self._logger = logging.getLogger("koshelek.parser")
        self._exporter = exporter or CSVExporter()
        self._session = self._initialize_session()
        self._authorise_session()

    @staticmethod
    def _is_exchange_row(tr_elem) -> bool:
        tds = tr_elem.find_all("td")
        return bool(tds[0].img)

    def __get_data_blocks(self, soup):
        trs = soup.find_all("tr", self.DATA_CLASS)
        data_blocks = filterfalse(self._is_exchange_row, trs)
        return data_blocks

    @staticmethod
    def __spending_from_data_block(self,
                                   data_block,
                                   spending_class=Income):
        td_els = data_block.find_all("td")
        title = td_els[0].a.text
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = split_currency(money)
        account = td_els[4].a.text
        date = td_els[5].a.text
        cost = spending_class(title=title, description="", category=category,
                              budget=budget, currency=cur, value=value,
                              account=account, date=date)
        return cost

    def parse_operations(self,
                         text: str,
                         op_type: str) -> Operations:
        """
        Extracts income or cost objects from the given HTML
        """
        operation_class = Cost if op_type == "cost" else Income
        soup = BeautifulSoup(text, "html.parser")
        data_blocks = self.__get_data_blocks(soup)
        func = partial(self.__spending_from_data_block,
                       spending_class=operation_class)
        costs = [func(b) for b in data_blocks]
        return list(costs)

    def get_operations_content(self, year="", month="", operation="cost"):
        if month and not year:
            year = datetime.datetime.now().year
        if not month and year:
            month = datetime.datetime.now().month
        if not (year or month):
            year = datetime.datetime.now().year
            month = datetime.datetime.now().month
        operation_type_url = self.URLS.get(operation, "cost")
        d = self.get_date_filter_dict_for_month(month, year)
        return self.get_url_content(operation_type_url, param_dict=d)

    def get_month_and_year_diff(self, cur_year, cur_month, month_count):
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
                                  months: int=1, operation="cost") -> Operations:
        """
        Get all costs or incomes within the range of
        given number of months from the current day.
        """
        if now is None:
            now = datetime.datetime.now()
        cur_month = now.month
        cur_year = now.year

        all_ops = []
        for diff_month_i in range(0, months):
            month, year = self.get_month_and_year_diff(cur_year, cur_month, diff_month_i)
            self._logger.info("Getting costs for {:02d}.{}".format(month, year))
            costs = self.get_operations_content(year=year, month=month,
                                                operation=operation)
            costs = self.parse_operations(costs, op_type=operation)
            all_ops.extend(costs)
        return all_ops

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
        self._session.get(self.BASE_URL)
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
        r = self._session.get(url, params=param_dict)
        assert r.status_code == HTTP_OK
        return r.text
