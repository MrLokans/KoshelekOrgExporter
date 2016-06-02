# coding: utf8

import os
import json
import argparse

from parser import KoshelekParser
from exporters import CSVExporter


CSV_DELIMETER = '|'

SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


def parse_args():
    arg_parser = argparse.ArgumentParser(description='Parse costs and income data from koshelek.org.')
    arg_parser.add_argument("--login",
                            help="Login for www.koshelek.org account.",
                            type=str)
    arg_parser.add_argument("--password",
                            help="Password for www.koshelek.org account.",
                            type=str)
    arg_parser.add_argument("--settings",
                            help="Path to JSON file with password and login.")
    args = arg_parser.parse_args()
    return args


def main():
    args = parse_args()
    if args.login and args.password:
        parser = KoshelekParser(username=args.login,
                                password=args.password,
                                exporter=CSVExporter())
    elif args.settings:
        assert os.path.exists(args.settings)
        assert os.path.isfile(args.settings)

        settings = json.load(open(args.settings))
        parser = KoshelekParser(username=settings["login"],
                                password=settings["password"],
                                exporter=CSVExporter())
    else:
        raise ValueError("Either login/password should be specified or settings file.")
    all_costs = parser.get_costs_for_months(months=2)
    parser.export_to_file(all_costs, "all_costs.csv", delimeter=CSV_DELIMETER)

if __name__ == '__main__':
    main()
