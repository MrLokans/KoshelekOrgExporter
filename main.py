# coding: utf8

import json

from parser import KoshelekParser
from exporters import CSVExporter


CSV_DELIMETER = '|'

SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


def main():
    parser = KoshelekParser(username=SETTINGS["login"],
                            password=SETTINGS["password"],
                            exporter=CSVExporter())
    all_costs = parser.get_costs_for_months(months=2)
    parser.export_to_file(all_costs, "all_costs.csv", delimeter="|")
    print(all_costs)

if __name__ == '__main__':
    main()
