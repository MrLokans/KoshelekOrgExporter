# coding: utf8

import os
import json
import argparse

from typing import Tuple

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
    arg_parser.add_argument("--login", "-l",
                            help="Login for www.koshelek.org account.",
                            type=str)
    arg_parser.add_argument("--password", "-p",
                            help="Password for www.koshelek.org account.",
                            type=str)
    arg_parser.add_argument("--settings", "-s",
                            help="Path to JSON file with password and login.")
    arg_parser.add_argument("--months", "-m",
                            help="Number of month to parse data for from the current month.",
                            default=0,
                            type=int)
    arg_parser.add_argument('--type', '-t',
                            help="Type of operations to log (spend/cost)",
                            default=None,
                            choices=['income', 'cost'])
    args = arg_parser.parse_args()
    return args


def read_settings(settings_file: str=SETTINGS_FILE):
    if not os.path.exists(settings_file) \
        or not os.path.isfile(settings_file):
        raise SettingsValidationError("Incorrect settings path.")
    settings = load_settings_from_file(settings_file)
    validate_settings_dict(settings)
    return settings


def get_credentials(cli_args) -> Tuple[str, str]:
    """
    Reads login and password from the CLI args
    """
    login, password = "", ""

    if cli_args.login and cli_args.password:
        login, password = cli_args.login, cli_args.password
    elif cli_args.settings:
        settings = read_settings(cli_args.settings)
        return settings["login"], settings["password"]
    else:
        settings = read_settings()
        login, password = settings["login"], settings["password"]
    return login, password


def main():
    args = parse_args()

    login, password = get_credentials(args)

    if not login or not password:
        msg = "Either login/password should be specified or settings file."
        raise ValueError(msg)

    parser = KoshelekParser(username=login,
                            password=password,
                            exporter=CSVExporter())

    if args.type:
        all_ops = parser.get_operations_for_months(months=args.months,
                                                   operation=args.type)
        parser.export_to_file(all_ops, "all_{}s.csv".format(args.type),
                              delimeter=CSV_DELIMETER)
    else:
        all_incomes = parser.get_operations_for_months(months=args.months,
                                                       operation="income")
        all_costs = parser.get_operations_for_months(months=args.months,
                                                       operation="cost")

        parser.export_to_file(all_costs, "all_costs.csv",
                              delimeter=CSV_DELIMETER)
        parser.export_to_file(all_incomes, "all_incomes.csv",
                              delimeter=CSV_DELIMETER)


if __name__ == '__main__':
    main()
