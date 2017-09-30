import abc
import decimal
import re
from typing import Iterator

from bs4 import BeautifulSoup

import constants
import utils
from operations import Account, Balance, Income, Cost, Exchange


class BaseStrategy(abc.ABC):

    @abc.abstractclassmethod
    def parse(cls, session, block):
        pass

    @staticmethod
    def _extract_id_from_url(ajax_url):
        indx = ajax_url.find(constants.URL_PART_BEFORE_ID) + len(constants.URL_PART_BEFORE_ID)
        ajax_url = ajax_url[indx:]
        return_url_pos = ajax_url.find('?return_url')
        if return_url_pos:
            ajax_url = ajax_url[:return_url_pos]
        return ajax_url


class IncomeParseStrategy(BaseStrategy):

    @classmethod
    def parse(cls, session, block):
        td_els = utils._extract_td_elements(block)
        ajax_url = utils._extract_ajax_url(block)
        # FIXME: moved to base class
        _id = cls._extract_id_from_url(ajax_url)
        title = td_els[0].a.text
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = utils.split_currency(money)
        account = td_els[4].a.text
        date = td_els[5].a.text
        return Income(id=_id, title=title, description="",
                      category=category, budget=budget,
                      currency=cur, value=value,
                      account=account, date=date)


class CostParseStrategy(BaseStrategy):

    @classmethod
    def parse(cls, session, block):
        td_els = utils._extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = utils._extract_ajax_url(block)
        _id = cls._extract_id_from_url(ajax_url)
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = utils.split_currency(money)
        account = td_els[4].a.text
        date = td_els[5].a.text
        return Cost(id=_id, title=title, description="", category=category,
                    budget=budget, currency=cur, value=value,
                    account=account, date=date)

    @staticmethod
    def _extract_id_from_url(ajax_url):
        indx = ajax_url.find(constants.URL_PART_BEFORE_ID) + len(constants.URL_PART_BEFORE_ID)
        return ajax_url[indx:]


class ExchangeParseStrategy(BaseStrategy):

    @classmethod
    def parse(cls, session, block) -> Exchange:
        td_els = utils._extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = utils._extract_ajax_url(block)
        _id = cls._extract_id_from_url(ajax_url)
        account_from, account_to = cls._parse_editorial_form(session, ajax_url)
        budget = td_els[2].a.text
        money = td_els[3].a.text
        cur, value = utils.split_currency(money)
        date = td_els[5].a.text
        # FIXME: fix description
        return Exchange(id=_id, title=title,
                        budget=budget, currency=cur, description='',
                        account_from=account_from, account_to=account_to,
                        value=value,
                        date=date)

    @staticmethod
    def _parse_editorial_form(session, ajax_url):
        response = session.get(constants.BASE_URL + ajax_url, verify=False)
        soup = BeautifulSoup(response.text, constants.DEFAULT_PARSER)

        account_from = soup\
            .find('select', id='accountFrom')\
            .find('option', selected='selected')\
            .text

        account_to = soup\
            .find('select', id='accountTo')\
            .find('option', selected='selected')\
            .text

        return account_to, account_from


class AccountParser:

    CURRENCY_URL = '/accounts/remainder_currency?account_id={}&currency={}'
    AVAILABLE_CURRENCIES = ('EUR', 'USD', 'BYR', 'BYN', 'RUR', 'PLN')

    def __init__(self, session):
        self.session = session

    def parse(self, block: BeautifulSoup) -> Account:
        details_url = self.__extract_details_url(block)
        return self.account_from_details_url(details_url)

    def account_from_details_url(self, details_url) -> Account:
        bs = BeautifulSoup(self.session.get(details_url).text)
        account_id = self.__extract_account_id(bs)
        account_title = self.__extract_account_title(bs)
        balances = [b for b in self.__extract_balances_for_account_id(account_id)]
        return Account(account_id, account_title, balances)

    def __extract_account_title(self, block: BeautifulSoup) -> str:
        return block.find('input', {'id': 'name'})['value']

    def __extract_details_url(self, block: BeautifulSoup) -> str:
        edit_action = block.find('img', {'alt': 'Редактировать'}).parent['onclick']
        details_url = re.search('\"(.+?)\"', edit_action).group().replace('"', '')
        return constants.BASE_URL + details_url

    def __extract_account_id(self, block: BeautifulSoup) -> str:
        action_url = block.find('form')['action']
        return re.search('\d{2,}', action_url).group()

    def __extract_balances_for_account_id(self, account_id: str) -> Iterator[Balance]:
        for cur_code in self.AVAILABLE_CURRENCIES:
            balance_url = constants.BASE_URL + self.CURRENCY_URL.format(account_id,
                                                                        cur_code)
            text = self.session.get(balance_url).text
            if text != '0.0':
                yield Balance(cur_code, decimal.Decimal(text))
