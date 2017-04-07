from bs4 import BeautifulSoup

import constants
import utils
from operations import Income, Cost, Exchange


class IncomeParseStrategy(object):

    @staticmethod
    def parse(session, block):
        td_els = utils._extract_td_elements(block)
        ajax_url = utils._extract_ajax_url(block)
        # FIXME: moved to base class
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
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

    @staticmethod
    def _extract_id_from_url(ajax_url):
        indx = ajax_url.find(constants.URL_PART_BEFORE_ID) + len(constants.URL_PART_BEFORE_ID)
        ajax_url = ajax_url[indx:]
        return_url_pos = ajax_url.find('?return_url')
        if return_url_pos:
            ajax_url = ajax_url[:return_url_pos]
        return ajax_url


class CostParseStrategy(object):

    @staticmethod
    def parse(session, block):
        td_els = utils._extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = utils._extract_ajax_url(block)
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
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


class ExchangeParseStrategy(object):

    @classmethod
    def parse(cls, session, block):
        td_els = utils._extract_td_elements(block)
        title = td_els[0].a.text
        ajax_url = utils._extract_ajax_url(block)
        _id = IncomeParseStrategy._extract_id_from_url(ajax_url)
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
