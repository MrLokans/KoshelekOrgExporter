# coding: utf8

import csv
import json
import datetime
import logging
from collections import namedtuple
from calendar import monthrange

import regex
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://koshelek.org"
LOGIN_URL = BASE_URL + "/login"
SESSION_COOKIE_NAME = "JSESSIONID"
COSTS_URL = BASE_URL + "/costs"
INCOMES_URL = BASE_URL + "/income"

DATA_CLASS = "data_line"

CSV_DELIMETER = '|'

SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


logging.basicConfig(level=logging.INFO)

RE_CURRENCY = regex.compile(r"(?P<currency>[\p{Alpha}$€]+)(?P<value>[\d ]+(\.|\,)\d{2})", regex.UNICODE)

Cost = namedtuple("Cost",
                  ["title", "description", "category",
                   "budget", "sum", "account", "date"])
Income = namedtuple("Income",
                    ["title", "description", "category",
                     "budget", "sum", "account", "date"])
Account = namedtuple("Account",
                     ["title", "description", "default_currency", "remnants"])


# TODO: add python2/3 compatibility layer

def initialize_session():
    session = requests.Session()
    return session


def authorise_session(session):
    session = requests.Session()

    # need it to obtain session cookie
    session.get(BASE_URL)

    session.post(LOGIN_URL, data={'user.login': SETTINGS['login'],
                                  'user.password': SETTINGS['password'],
                                  'saveUser': True})
    return session


def get_month_and_year_diff(cur_year, cur_month, month_count):
    month_diff = cur_month - month_count
    year = cur_year
    month = month_diff
    if month_diff <= 0:
        month = 12 - abs(month_diff) % 12
        year = cur_year - abs(month_diff) // 12 - 1
    return (month, year)


def get_costs_for_months(session, months):
    """Gets all costs within the given number of months"""
    now = datetime.datetime.now()
    cur_month = now.month
    cur_year = now.year

    all_costs = []
    for diff_month_i in range(0, months):
        month, year = get_month_and_year_diff(cur_year, cur_month, diff_month_i)
        logging.info("Getting costs for {:02d}.{}".format(month, year))
        costs = get_costs_content(session, year=year, month=month)
        all_costs.extend(parse_costs(costs))
    return all_costs


def get_costs_content(session, year="", month=""):
    if month and not year:
        year = datetime.datetime.now().year
    if not month and year:
        month = datetime.datetime.now().month
    if not (year or month):
        year = datetime.datetime.now().year
        month = datetime.datetime.now().month

    d = get_date_filter_dict_for_month(month, year)
    return get_url_content(session, COSTS_URL, param_dict=d)


def get_date_filter_dict_for_month(month_num, year):
    """Generate filter date parameters for URL.
    Assume that you want to get statistics for the march of 2015:
    pass 3, 2015 as params and you will get dict {"filtrDateStart": "01.03.2015", "filtrDateEnd": "31.03.2105"}
    that cand be passed as param for the date request
    """
    # TODO: cover with tests
    month = int(month_num)
    year = int(year)
    __, days_count = monthrange(year, month)
    return {"filtrDateStart": "01.{:02d}.{}".format(month, year),
            "filtrDateEnd": "{}.{:02d}.{}".format(days_count, month, year)}


def get_incomes_content(session):
    return get_url_content(session, INCOMES_URL)


def get_url_content(session, url, param_dict=None):
    if not param_dict:
        param_dict = {}
    r = session.get(url, params=param_dict)
    assert r.status_code == 200
    return r.text


def is_exchange_row(tr_elem):
    tds = tr_elem.find_all("td")
    return bool(tds[0].img)


def parse_costs(text):
    soup = BeautifulSoup(text, "html.parser")
    data_blocks = filter(lambda x: not is_exchange_row(x), soup.find_all("tr", DATA_CLASS))

    costs = []
    for block in data_blocks:
        td_els = block.find_all("td")
        # TODO: use a table to avoid code duplication
        name = td_els[0].a.text
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        account = td_els[4].a.text
        date = td_els[5].a.text
        costs.append(Cost(title=name, description="", category=category,
                          budget=budget, sum=money, account=account, date=date))
    return costs


# TODO: logics is complitely duplicated from costs parser, rethink
def parse_incomes(text):
    soup = BeautifulSoup(text, "html.parser")
    data_blocks = filter(lambda x: not is_exchange_row(x), soup.find_all("tr", DATA_CLASS))

    incomes = []
    for block in data_blocks:
        td_els = block.find_all("td")
        # TODO: use a table to avoid code duplication
        name = td_els[0].a.text
        category = td_els[1].a.text
        budget = td_els[2].a.text
        money = td_els[3].a.text
        account = td_els[4].a.text
        date = td_els[5].a.text
        incomes.append(Income(title=name, description="", category=category,
                              budget=budget, sum=money,
                              account=account, date=date))
    return incomes


def export_costs_to_csv(costs, csv_file="costs.csv"):
    # Description and title may contain commas
    with open(csv_file, "w") as csv_f:
        writer = csv.writer(csv_f, delimiter=CSV_DELIMETER)
        writer.writerow(['Title', 'Description', 'Category', 'Budget', 'Currency', 'Sum', 'Account', 'Date'])

        for cost in costs:
            sum_str = cost.sum.replace('\xa0', ' ')
            cur, val = split_currency(sum_str)
            val = val.replace(',', '.').replace(' ', '')
            writer.writerow([cost.title, cost.description, cost.category,
                             cost.budget, cur, val, cost.account, cost.date])


def split_currency(cur_str):
    match = RE_CURRENCY.match(cur_str)
    if not match:
        raise ValueError("Incorrect currency str: {}".format(cur_str))
    cur = match.groupdict()['currency']
    value = match.groupdict()['value']
    return cur, value


def main():
    session = initialize_session()
    session = authorise_session(session)
    # costs_text = get_costs_content(session)
    # costs = parse_costs(costs_text)

    # incomes_text = get_incomes_content(session)
    # incomes = parse_incomes(incomes_text)

    # export_costs_to_csv(costs)
    all_costs = get_costs_for_months(session, 20)
    export_costs_to_csv(all_costs, csv_file="all_costs.csv")

if __name__ == '__main__':
    main()
