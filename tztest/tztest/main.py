"""Save and load some timestamps to Postgres using different
techniques and see if we get back the timestamps we want.
"""

from datetime import datetime
from pytz import timezone
from pytz import UTC

from tztest.tztest.models import Timestamp

from django.conf import settings

DJANGO_TZ = timezone(settings.TIME_ZONE)


class SaveMethod(object):
    """
    A way of saving a datetime to the database. The tz argument
    is the time zone to use and the style determines whether to
    save an 'aware' or 'naive' datetime.
    """
    def __init__(self, tz, style):
        assert style in ('aware', 'naive')
        self.tz = tz
        self.style = style

    def __unicode__(self):
        return u'{} {}'.format(self.style, self.tz.zone)

    def save(self, dt):
        dt = self.tz.normalize(dt)
        if self.style == 'naive':
            dt = dt.replace(tzinfo=None)
        return Timestamp.objects.create(timestamp=dt)


class LoadMethod(object):
    """
    A way of loading a datetime from the database. The tz argument is
    the time zone to localize to and the conversion argument
    determines whether to use the 'implicit' conversion of the Postgres
    connection (the normal Django way) or to use an 'explicit'
    conversion in an extra select.
    """
    def __init__(self, tz, conversion):
        assert conversion in ('implicit', 'explicit')
        self.tz = tz
        self.conversion = conversion

    def __unicode__(self):
        return u'{} {}'.format(self.conversion, self.tz.zone)

    def load(self, timestamp):
        """Return (stored_datetime, loaded_datetime).

        The stored_datetime is the timestamp actually stored in
        Postgres, which may or may not be the timestamp we saved. The
        loaded_datetime is the timestamp we end up with using this
        method.
        """
        select = {
            'timestamp_explicit':
            "timestamp at time zone '{}'".format(self.tz.zone),
            'timestamp_stored': "timestamp at time zone 'UTC'",
        }

        loaded_attr = ('timestamp' if self.conversion == 'implicit'
                       else 'timestamp_explicit')

        qs = Timestamp.objects.extra(select=select)

        timestamp = qs.get(pk=timestamp.pk)

        stored_datetime = UTC.localize(timestamp.timestamp_stored)
        loaded_datetime = self.tz.localize(getattr(timestamp, loaded_attr))

        return stored_datetime, loaded_datetime


class TestResult(object):
    """
    The result of a single roundtrip test.
    """
    def __init__(self, saved_dt, stored_dt, loaded_dt):
        self.stored_correctly = saved_dt == stored_dt
        self.loaded_correctly = saved_dt == loaded_dt

        self.stored_error = stored_dt - saved_dt
        self.loaded_error = loaded_dt - saved_dt

    def __unicode__(self):
        return u'{}/{}'.format(
            'OK' if self.stored_correctly else self.stored_error,
            'OK' if self.loaded_correctly else self.loaded_error)


class Test(object):
    """
    A pair of methods for saving and loading a timestamp to the database.
    """
    next_test_number = 1

    def __init__(self, save_method, load_method):
        self.test_number, Test.next_test_number = (
            self.next_test_number, self.next_test_number + 1)
        self.save_method = save_method
        self.load_method = load_method

    def __unicode__(self):
        return unicode(self.test_number)

    def make_roundtrip(self, saved_dt):
        return self.load_method.load(self.save_method.save(saved_dt))

    def run_test(self, saved_dt):
        return TestResult(saved_dt, *self.make_roundtrip(saved_dt))


class TestTable(object):
    """
    A table showing the results of saving and loading different
    timestamps using different save and load methods.
    """
    def __init__(self):
        self.headers = ['#', 'Save As', 'Load As']
        self.rows = []

    def add_datetime(self, dt):
        """Add a test datetime to the table and update the results."""
        self.headers.append(DJANGO_TZ.normalize(dt))
        for row in self.rows:
            row.append(row[0].run_test(dt))

    def add_test(self, test):
        """Add a Test to the table and update the results."""
        row = [test, test.save_method, test.load_method]
        self.rows.append(row)
        for dt in self.headers[3:]:
            row.append(test.run_test(dt))

    def __unicode__(self):
        lines = []

        def add_row(row):
            cols = [
                u'{:>2}'.format(row[0]),
                u'{:^18}'.format(row[1]),
                u'{:^21}'.format(row[2]),
            ]
            cols.extend(u'{:^27}'.format(unicode(val)) for val in row[3:])
            lines.append(u'|'.join(cols))

        add_row(self.headers)
        lines.append('-' * len(lines[0]))
        map(add_row, self.rows)

        return u'\n'.join(lines)


datetimes = [
    # A timestamp that happens shortly before a US/Pacific
    # daylight savings time fall-back event.
    datetime(2002, 10, 27, 8, 30, 0, tzinfo=UTC),

    # A timestamp whose naive version, when interpreted as if
    # it was in US/Pacific, happens shortly after a daylight
    # savings time fall-forward event.
    datetime(2002, 4, 7, 2, 30, 0, tzinfo=UTC),
]

tests = [
    Test(SaveMethod(DJANGO_TZ, 'naive'), LoadMethod(DJANGO_TZ, 'implicit')),
    Test(SaveMethod(DJANGO_TZ, 'naive'), LoadMethod(DJANGO_TZ, 'explicit')),
    Test(SaveMethod(DJANGO_TZ, 'aware'), LoadMethod(DJANGO_TZ, 'implicit')),
    Test(SaveMethod(DJANGO_TZ, 'aware'), LoadMethod(DJANGO_TZ, 'explicit')),
    Test(SaveMethod(DJANGO_TZ, 'naive'), LoadMethod(UTC, 'explicit')),
    Test(SaveMethod(UTC, 'aware'),       LoadMethod(DJANGO_TZ, 'implicit')),
    Test(SaveMethod(UTC, 'naive'),       LoadMethod(UTC, 'implicit')),
    Test(SaveMethod(UTC, 'aware'),       LoadMethod(UTC, 'explicit')),
    Test(SaveMethod(DJANGO_TZ, 'aware'), LoadMethod(UTC, 'explicit')),
]


def generate_test_table():
    table = TestTable()

    for dt in datetimes:
        table.add_datetime(dt)

    for test in tests:
        table.add_test(test)

    return table
