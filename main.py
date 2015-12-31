import json
from collections import namedtuple

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://koshelek.org"
LOGIN_URL = BASE_URL + "/login"
SESSION_COOKIE_NAME = "JSESSIONID"
COSTS_URL = BASE_URL + "/costs"
INCOMES_URL = BASE_URL + "/income"

DATA_CLASS = "data_line"


SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


Cost = namedtuple("Cost", ["title", "description", "category", "budget", "sum", "account", "date"])
Income = namedtuple("Income", ["title", "description", "category", "budget", "sum", "account", "date"])
Account = namedtuple("Account", ["title", "description", "default_currency", "remnants"])


def initialize_session():
    session = requests.Session()
    return session


def authorise_session(session):
    session = requests.Session()

    # need it to obtain session cookie
    session.get(BASE_URL)

    session.post(LOGIN_URL, data={'user.login': SETTINGS['login'], 'user.password': SETTINGS['password'], 'saveUser': True})
    return session


def get_costs_content(session):
    return get_url_content(session, COSTS_URL)


def get_incomes_content(session):
    return get_url_content(session, INCOMES_URL)


def get_url_content(session, url):
    r = session.get(url)
    assert r.status_code == 200
    return r.text


def parse_costs(text):
    soup = BeautifulSoup(text, "html.parser")
    data_blocks = soup.find_all("tr", DATA_CLASS)

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


def parse_incomes(text):
    soup = BeautifulSoup(text, "html.parser")
    data_blocks = soup.find_all("tr", DATA_CLASS)

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
                              budget=budget, sum=money, account=account, date=date))
    return incomes


def main():
    session = initialize_session()
    session = authorise_session(session)
    costs_text = get_costs_content(session)
    costs = parse_costs(costs_text)

    incomes_text = get_incomes_content(session)
    incomes = parse_incomes(incomes_text)
    print(costs)
    print(incomes)


if __name__ == '__main__':
    main()
