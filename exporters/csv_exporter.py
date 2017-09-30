import csv
import itertools
import typing
from collections import namedtuple


class CSVExporter(object):

    @staticmethod
    def export_to_file(costs: typing.Sequence[namedtuple],
                       filename: str,
                       **kwargs):
        delimiter = kwargs.get('delimeter', ',')
        # Description and title may contain commas
        with open(filename, "w") as csv_f:
            if not costs:
                return
            first = next(iter(costs))
            writer = csv.writer(csv_f, delimiter=delimiter)
            writer.writerow(first._fields)

            for cost in itertools.chain([first], costs):
                values = [getattr(cost, field)
                          for field in first._fields]
                writer.writerow(values)
