# coding: utf8

import json

from parser import KoshelekParser


CSV_DELIMETER = '|'

SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


def main():
    parser = KoshelekParser(SETTINGS["login"], SETTINGS["password"])
    all_costs = parser.get_costs_for_months(months=2)
    print(all_costs)

if __name__ == '__main__':
    main()
