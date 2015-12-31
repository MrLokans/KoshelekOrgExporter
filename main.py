import json
from collections import namedtuple

import requests
import bs4

BASE_URL = "https://koshelek.org"
LOGIN_URL = BASE_URL + "/login"
SESSION_COOKIE_NAME = "JSESSIONID"

COSTS_URL = BASE_URL + "/costs"


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
    r = session.get(COSTS_URL)
    assert r.status_code == 200
    return r.text


def main():
    session = initialize_session()
    session = authorise_session(session)
    authorise_session()
    costs_text = get_costs_content(session)


if __name__ == '__main__':
    main()
