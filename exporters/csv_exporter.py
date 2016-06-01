import csv


class CSVExporter(object):

    @staticmethod
    def export_to_file(costs, filename, **kwargs):
        delimiter = kwargs.get('delimeter', ',')
        # Description and title may contain commas
        with open(filename, "w") as csv_f:
            writer = csv.writer(csv_f, delimiter=delimiter)
            writer.writerow(['Title', 'Description', 'Category', 'Budget',
                             'Currency', 'Sum', 'Account', 'Date'])

            for cost in costs:
                writer.writerow([cost.title, cost.description, cost.category,
                                 cost.budget, cost.currency, cost.value,
                                 cost.account, cost.date])
