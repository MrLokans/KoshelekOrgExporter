# coding: utf8

import os
import json
import argparse

from exceptions import SettingsValidationError
from parser import KoshelekParser
from exporters import CSVExporter


CSV_DELIMETER = '|'

SETTINGS_FILE = "settings.json"
SETTINGS = json.load(open(SETTINGS_FILE))


def load_settings_from_file(filepath):
    with open(filepath) as settings_fh:
        return json.load(settings_fh)


def validate_settings_dict(settings_dict):
    """
    Check whether settings dict has all the required fields
    """
    required_fields = ("login", "password")
    if not all(x in settings_dict for x in required_fields):
        msg = "Incorrect settings, following fields are required: {}."
        raise SettingsValidationError(msg.format(", ".join(required_fields)))


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

        settings = load_settings_from_file(args.settings)
        validate_settings_dict(settings)

        parser = KoshelekParser(username=settings["login"],
                                password=settings["password"],
                                exporter=CSVExporter())
    elif os.path.exists(SETTINGS_FILE) and os.path.isfile(SETTINGS_FILE):
        settings = load_settings_from_file(SETTINGS_FILE)
        validate_settings_dict(settings)

        parser = KoshelekParser(username=settings["login"],
                                password=settings["password"],
                                exporter=CSVExporter())
    else:
        msg = "Either login/password should be specified or settings file."
        raise ValueError(msg)
    all_costs = parser.get_costs_for_months(months=2)
    parser.export_to_file(all_costs, "all_costs.csv", delimeter=CSV_DELIMETER)

if __name__ == '__main__':
    main()
