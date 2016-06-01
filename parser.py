import datetime
import logging
from calendar import monthrange
from collections import namedtuple
from functools import partial
from itertools import filterfalse

import regex
import requests
from bs4 import BeautifulSoup


RE_CURRENCY = regex.compile(r"(?P<currency>[\p{Alpha}$€]+)(?P<value>[\d ]+(\.|\,)\d{2})", regex.UNICODE)


def split_currency(sum_str):
    sum_str = sum_str.replace('\xa0', ' ')
    match = RE_CURRENCY.match(sum_str)
    if not match:
        raise ValueError("Incorrect currency str: {}".format(sum_str))
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


class IncorrectCredentials(ValueError):
    pass


class KoshelekParser(object):

    BASE_URL = "https://koshelek.org"
    LOGIN_URL = BASE_URL + "/login"
    SESSION_COOKIE_NAME = "JSESSIONID"
    COSTS_URL = BASE_URL + "/costs"
    INCOMES_URL = BASE_URL + "/income"

    DATA_CLASS = "data_line"

    def __init__(self, username="", password="", exporter=None):
        # TODO: add default exporter
        if not (username and password):
            msg = "Password or username is empty."
            raise IncorrectCredentials(msg)
        self.username = username
        self.password = password
        self._logger = logging.getLogger("koshelek.parser")
        self._session = self._initialize_session()
        self._authorise_session()

    def _is_exchange_row(self, tr_elem):
        tds = tr_elem.find_all("td")
        return bool(tds[0].img)

    def __get_data_blocks(self, soup):
        trs = soup.find_all("tr", self.DATA_CLASS)
        data_blocks = filterfalse(self._is_exchange_row, trs)
        return data_blocks

    def __spending_from_data_block(self, data_block, spending_class=Income):
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

    def parse_costs(self, text):
        soup = BeautifulSoup(text, "html.parser")
        data_blocks = self.__get_data_blocks(soup)
        func = partial(self.__spending_from_data_block, spending_class=Cost)
        costs = [func(b) for b in data_blocks]
        return list(costs)

    # TODO: logics is completely duplicated from costs parser, rethink
    def parse_incomes(self, text):
        soup = BeautifulSoup(text, "html.parser")
        data_blocks = self.__get_data_blocks(soup)
        func = partial(self.__spending_from_data_block, spending_class=Income)
        costs = [func(b) for b in data_blocks]
        return list(costs)

    def get_costs_content(self, year="", month=""):
        if month and not year:
            year = datetime.datetime.now().year
        if not month and year:
            month = datetime.datetime.now().month
        if not (year or month):
            year = datetime.datetime.now().year
            month = datetime.datetime.now().month

        d = self.get_date_filter_dict_for_month(month, year)
        return self.get_url_content(self.COSTS_URL, param_dict=d)

    def get_month_and_year_diff(self, cur_year, cur_month, month_count):
        month_diff = cur_month - month_count
        year = cur_year
        month = month_diff
        if month_diff <= 0:
            month = 12 - abs(month_diff) % 12
            year = cur_year - abs(month_diff) // 12 - 1
        return (month, year)

    def get_date_filter_dict_for_month(self, month_num, year):
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

    def get_costs_for_months(self, now=None, months=1):
        """Gets all costs within the  range of
        given number of months from today"""
        if now is None:
            now = datetime.datetime.now()
        cur_month = now.month
        cur_year = now.year

        all_costs = []
        for diff_month_i in range(0, months):
            month, year = self.get_month_and_year_diff(cur_year, cur_month, diff_month_i)
            self._logger.info("Getting costs for {:02d}.{}".format(month, year))
            costs = self.get_costs_content(year=year, month=month)
            costs = self.parse_costs(costs)
            all_costs.extend(costs)
        return all_costs

    @staticmethod
    def _initialize_session():
        session = requests.Session()
        return session

    def _authorise_session(self):
        """Sets required cookies for the session"""
        self._session.get(self.BASE_URL)

        payload = {
            'user.login': self.username,
            'user.password': self.password,
            'saveUser': True
        }
        self._session.post(self.LOGIN_URL, data=payload)
        return self._session

    def get_url_content(self, url, param_dict=None):
        if not param_dict:
            param_dict = {}
        r = self._session.get(url, params=param_dict)
        assert r.status_code == 200
        return r.text
