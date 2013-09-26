"""Print out a table of timestamps, some methods of saving and loading
them, and whether each method ended up storing and loaded the same
timestamps it started with. For each method and timestamp, the table
shows 'OK' if the stored/loaded timestamp is the same as the one
saved. Otherwise, the difference between the stored/loaded timestamp
is shown. Only the last two methods where all four such timestamps are
OK pass the test.
"""

from django.core.management.base import BaseCommand

from tztest.tztest.main import generate_test_table


class Command(BaseCommand):

    help = __doc__

    def handle(self, *args, **opts):
        print unicode(generate_test_table())
