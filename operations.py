from collections import namedtuple
from typing import List, Union


Cost = namedtuple("Cost",
                  ["id", "title", "description", "category",
                   "budget", "currency", "value", "account", "date"])
Income = namedtuple("Income",
                    ["id", "title", "description", "category",
                     "budget", "currency", "value", "account", "date"])
Exchange = namedtuple("Exchange",
                      ["id", "title", "description", "budget", "currency",
                       "value", "account_from", "account_to", "date"])
Account = namedtuple("Account",
                     ["id", "title", "remnants"])
Balance = namedtuple("Balance",
                     ["currency", "value"])

Operations = List[Union[Income, Cost]]
