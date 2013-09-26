Django models support storing timestamps using [`DateTimeField`](https://docs.djangoproject.com/en/1.5/ref/models/fields/#datetimefield) attributes.
The behavior of these fields with regards to time zones is controlled by the Django settings [`USE_TZ`](https://docs.djangoproject.com/en/1.5/ref/settings/#use-tz) and [`TIME_ZONE`](https://docs.djangoproject.com/en/1.5/ref/settings/#time-zone).

There are some very subtle issues that are important to be aware of if you are runnning Django with a setting of `USE_TZ = False` (the default if you do not explicitly set it) and a `TIME_ZONE` setting in a time zone with daylight savings time, such as US Pacific Time.

This example application illustrates some of the issues that can crop up when using the Postgres database.


## Timestamps in Python

Timestamps are represented in Python using [datetime.datetime](http://docs.python.org/2.7/library/datetime.html#datetime-objects) objects. Datetime objects come in two flavors, *naive* and *aware*. A naive datetime object has no time zone information and so either the time zone is implicit or the datetime represents an abstract time (like, say, midnight on Halloween in 2012) that happened at multiple absolute times in the different time zones around the world. An aware datetime has time zone information and thus represents a particular fixed point in time. Modulo [relativity](http://en.wikipedia.org/wiki/Theory_of_relativity) and all that.

Python datetime objects support date calculations and comparisons so that you can project a datetime into the future or past or compare one datetime with another. There is an important restriction to know about datetime comparisons: you can only compare a datetime with another of the same flavor. To do otherwise will raise an exception.


## Datetimes in Django

If `USE_TZ` is `True` Django will populate `DateTimeField` attributes loaded from the database with aware datetimes in [UTC](http://en.wikipedia.org/wiki/Coordinated_Universal_Time), a canonical time zone that has no daylight savings time. It will also use aware datetimes in UTC to initialize `DateTimeField` attributes that have [`auto_now`](https://docs.djangoproject.com/en/1.5/ref/models/fields/#datetimefield) or [`auto_now_add`](https://docs.djangoproject.com/en/1.5/ref/models/fields/#datetimefield) set to `True`. Because of the restriction on datetime comparisons noted above, when using `USE_TZ = True` it makes sense to work with aware datetimes throughout your project.

If `USE_TZ` is `False`, Django will load naive datetimes from the database and use naive datetimes to populate `auto_now` fields. Django will arrange for those datetimes to be implicitly in the time zone given by the `TIME_ZONE` setting, and it will assume that any naive datetimes you provide yourself are also in that time zone.

Once you have chosen whether to use aware or naive datetimes, and your codebase has grown large, it is not so easy to change your mind. As a global setting, `USE_TZ` affects all `DateTimeField` attributes in all your models in your project at once. And the rest of your code is probably using the same flavor of datetime fields that you chose with Django, to avoid datetime comparison problems. Flipping the setting is not something that can be undertaken lightly.

So choose this setting with care! Using naive datetimes is not recommended [by django] (https://docs.djangoproject.com/en/1.5/topics/i18n/timezones/) nor [by pytz](https://pypi.python.org/pypi/pytz/), a popular python implementation of the time zone database that Django will use if it is available. So the short answer is, choose `USE_TZ = True`, which is the setting you now get when initializing a new project with `django-admin.py startproject`.

However, the `USE_TZ` setting was not introduced until Django 1.4. Prior to that release Django would use naive datetimes exclusively. So if you have a Django project started before version 1.4 then you probably have `USE_TZ = False` (perhaps implicitly by not setting it) and are using naive datetimes. Furthermore, at this point it is probably not so easy to change.

This sample project illustrates some subtle problems you can run into when using Django and Postgres with naive datetimes in a time zone with daylight savings time. Similar problems would likely occur with other databases as well, but this example uses Postgres when delving into the details.

This project also shows one way to circumvent the probem for an individual datetime attribute without changing the Django time zone-related settings.

The rest of this document assumes you are using Django with `USE_TZ = False` and `TIME_ZONE = 'US/Pacific'`, but any time zone with daylight savings time would present similar issues.


## Timestamps in Postgres

Postgres supports [lots](http://www.postgresql.org/docs/9.2/static/datatype-datetime.html) of different time- and date- related fields. But for this example we only care about the one that Django uses for `DateTimeField` attributes: `timestamp with time zone`.

Postgres [_always_ stores `timestamp with time zone values` in UTC](http://www.postgresql.org/docs/9.2/static/datatype-datetime.html#DATATYPE-TIMEZONES). This is completely independent of the Django time zone settings, so even if you have `USE_TZ = False` and you are using a non-UTC `TIME_ZONE` setting, your timestamps are being stored in UTC in your database if you are using Postgres or another database that also stores timestamps in UTC exclusively.


How Django saves a timestamp to Postgres
----------------------------------

When a datetime value is being prepared to send to the database, Django will call [`get_prep_value`](https://github.com/django/django/blob/stable/1.5.x/django/db/models/fields/__init__.py#L819). This function will check the `USE_TZ` setting. Since that is `False`, `get_prep_value` will simply return the datetime unchanged.

Now django will use [`get_db_prep_value`](https://github.com/django/django/blob/stable/1.5.x/django/db/models/fields/__init__.py#L832) and this function will convert the datetime using the [`value_to_db_datetime`](https://github.com/django/django/blob/stable/1.5.x/django/db/backends/__init__.py#L840) method (the postgres_psycopg2 backend does not override the default version of that method).

The `value_to_db_datetime` method will convert the datetime using the [`six.text_type`](https://bitbucket.org/gutworth/six/src/69df1f152215a67e8942f8616772923308e33b80/six.py?at=default#cl-47) function which on Python 2 is simply the `unicode` function.

The `unicode` representation of a datetime object is the ISO 8601 text representation of that datetime. That representation includes the time zone offset if and only if the datetime object is timezone aware. Examples:

```
../manage.py shell
In [1]: from django.db import connection

In [2]: import datetime

In [3]: connection.ops.value_to_db_datetime(datetime.datetime.now())
Out[3]: u'2013-09-23 06:44:52.057625'

In [4]: connection.ops.value_to_db_datetime(datetime.datetime.utcnow())
Out[4]: u'2013-09-23 13:45:03.798541'

In [5]: import pytz

In [6]: UTC = pytz.UTC

In [7]: US_PACIFIC = pytz.timezone('US/Pacific')

In [8]: connection.ops.value_to_db_datetime(US_PACIFIC.localize(datetime.datetime.now()))
Out[8]: u'2013-09-23 06:46:11.219893-07:00'

In [9]: connection.ops.value_to_db_datetime(UTC.localize(datetime.datetime.utcnow()))
Out[9]: u'2013-09-23 13:46:27.239856+00:00'
```

So the value that Django hands to the psycopg2 database adaptor for a datetime object is the `unicode` string with the ISO 8601 representation of the exact datetime object we set on the model field. And since that value is simply a string rather than a datetime object, psycopg2 sends it directly to Postgres without further modification.

If the ISO string contains a time zone offset, Postgres will interpret the timestamp using that explicit time zone regardless of any database settings. If the string does not contain time zone information then Postgres will assume the timestamp is in the [time zone](http://www.postgresql.org/docs/9.2/static/runtime-config-client.html#GUC-TIMEZONE) setting of the database (or connection).

The default Postgres timezone setting is `'GMT'`, but you can set it to another time zone in the `postgresql.conf` file. You can also configure the setting on a per-connection basis and Django does just that. When the Django psycopg2 backend [makes a database cursor](https://github.com/django/django/blob/stable/1.5.x/django/db/backends/postgresql_psycopg2/base.py#L184-L205) Django will set the Postgres connection time zone setting to the _Django_ `TIME_ZONE` setting which in our current example is `'US/Pacific'`. Note that Django would use UTC (basically the same as GMT) if `settings.USE_TZ` were `True`.

Thus, when using Django with `USE_TZ = False`, if you save a naive datetime object on a Django `DateTimeField` attribute, Postgres will store it in UTC after converting it _as if it were originally in the `settings.TIME_ZONE` time zone_.


## How Django loads a timestamp from Postgres

The other purpose of the Postgres time zone setting is determining how to send timestamp values back to the client. If you don't specifically request a particular time zone, Postgres will convert timestamps to the time zone setting of the connection. Such timestamps will actually have time zone offset information and psycopg2 can create aware datetimes from them. But when `settings.USE_TZ` is `False`, Django [ignores](https://github.com/django/django/blob/stable/1.5.x/django/db/backends/postgresql_psycopg2/base.py#L204) the time zone offset and simply constructs a naive Python datetime from the timestamp.

It is also possible to tell Postgres to return a particular timestamp value in whatever time zone you want _per query_ and independent of the Postgres time zone setting by using the [`at time zone`](http://www.postgresql.org/docs/9.2/static/functions-datetime.html#FUNCTIONS-DATETIME-ZONECONVERT) syntax. Such a timestamp does not include any time zone information at all.

Django does not use the `at time zone` syntax when constructing queries and thus if `USE_TZ` is `False` the timestamps that Django loads are converted (by Postgres) to the `settings.TIME_ZONE` time zone (remember Django configures the database connection with that time zone) and stored on your models as naive Python datetimes.


## Running the test

To run the test, create a new Postgres database called `tztest`:

```shell
# createdb tztest
```

Now ask Django to populate the database:

```shell
# ../manage.py syncdb
```

Now you can run the test on the command line:

```shell
# ../manage.py tztest_test
```

This will print out the results in an ASCII table.

You can also see the results in beautiful HTML by starting the Django webserver:

```shell
# ../manage.py runserver 8000
```

And then pointing your browser to http://localhost:8000.


## What the test does

The test stores some timestamps to the database using the Django ORM and then loads them back again. Each time it does this it checks to see if the timestamp that got stored in Postgres and the timestamp we got back are the same timestamp we originally put in. It performs this test using different timestamps and a variety of methods.

The methods are divided into 'save' methods and 'load' methods. For the save methods, we can decide whether to give Django an aware or a naive datetime and which timezone that datetime object will be in.

Because we are using `settings.USE_TZ = False`, all the datetime objects we get back from a Django query will be naive. So for the load methods we can decide which time zone to interpret those naive timestamps with, and whether to let Postgres implicitly convert the timestamp to the database connection time zone setting (which is also the Django `TIME_ZONE` setting), or to explicitly request a timestamp in a particular time zone using the Django queryset [`extra`](https://docs.djangoproject.com/en/1.5/ref/models/querysets/#extra) method.

We use two different timestamps for the test. The first one (`2002-10-27 01:30:00-07:00`) is a half hour before a daylight savings time "fall back" event in the United States in which the clocks went from 01:59:59 to 01:00:00. This is an interesting timestamp because a naive datetime object that represents it in US/Pacific is fundamentally ambiguous since that clock reading happens on two separate times an hour apart. Even just knowing the datetime is in US/Pacific isn't enough to tell you which specific time it refers to -- you need to know whether daylight savings time was in effect or not.

The second timestamp is a little more unusual. The timestamp itself (`2002-04-06 18:30:00-08:00`) isn't particularly interesting in any of the United States time zones. But take the naive version of that timestamp in UTC (`2002-04-07T02:30:00+00:00`) and pretend it is in US/Pacific. That pretend time happens shortly after a daylight savings time "fall forward" event in which the clocks went from 01:59:59 to 03:00:00. The reason we chose this time for the test will become clear below, but it's interesting because technically that US/Pacific clock reading never actually happened.


## The Results

After running the test you should find that all but the last two methods have failed on one or the other of the test timestamps. Let's go through them and find out why.

#### Method #1

Method #1 saves timestamps as naive datetime objects in US/Pacific and then loads them with a standard Django ORM `get` request. This is the way that a Django project with `USE_TZ = False` is probably saving and loading datetimes. As we have seen, this will result in the datetime being converted to UTC and then back to US/Pacific, at which point it is handed to us in the form of a naive datetime object. And because of the ambiguous nature of the first test timestamp, we end up storing the wrong time in the database and getting the wrong time back. The stored and loaded versions of the first datetime are an hour later than the one we put it. This doesn't happen with the second test timestamp. Only those just before the fall-back event will be wrong.

Note that the naive datetime object we get back from Django is identical to the naive datetime we saved. But that naive datetime could represent two different absolute points in time. If we were to "fix" this particular test by always assuming it represents the pre-fallback time then the method would fail when we tried to store the post-fallback time with the identical naive representation. There simply isn't enough information to choose the right one every time.

#### Method #2

Method #2 uses the same save method but on load it explicitly tells Postgres to convert the timestamp to US/Pacific. But this won't work because Postgres was already implicitly converting the timestamp to US/Pacific so it ends up with the same problems.

#### Methods #3 and #4

Methods #3 and #4 try using an aware US/Pacific datetime when saving and using the load methods of #1 and #2. They work a bit better and actually store the correct timestamp in Postgres since there is no implicit conversion happening during the save step. But they still get caught by the fact that the datetime is being loaded without time zone information and ends up as the wrong timestamp.

#### Method #5

Method #5 tries to deal with the lack of time zone information during the load step by explicitly telling Postgres to return a timestamp in UTC. Since UTC does not have daylight savings time, a naive UTC datetime is not ambiguous and we will load the exact UTC time that Postgres ended up storing. But #5 tries to get away with using a naive US/Pacific datetime when saving. Since that stores the incorrect timestamp, we get back the incorrect one as well. Fail!

#### Method #6

Method #6 throws up its hands and gives Django an aware datetime object in UTC to store in Postgres. This is guaranteed to store the correct UTC time in the database, just like when we used an aware US/Pacific datetime. But #6 lets Django give us an implicit US/Pacific datetime back again and we fail.

#### Method #7

Method #7 is interesting. Here we give Django an *implicit* UTC datetime to save to the database and then interpret the naive datetime that Django gives back in UTC as well. This represents an attempt to "do the right thing" by always working with UTC internally. And if Django and Postgres stored a naive datetime exactly as we provided it, all would be well. Indeed, the method is the first one that actually loads the correct timestamp for the first datetime.

But #7 has some big problems. The timestamps actually stored in Postgres are a full 8 hours ahead of the timestamps we tried to save. Remember, Postgres is going to convert any naive timestamp we give it _as if_ it was in US/Pacific. These happen to be in UTC, but Postgres doesn't know that. So the timestamps that Postgres stores are way off, not just by an hour.

When #7 loads the first datetime, Postgres converts the timestamp it actually stored back to US/Pacific, thus undoing the incorrect conversion to UTC it originally performed and when we interpret that naive datetime in UTC we get our original timestamp back. Most timestamps saved with method #7 would load correctly, even if they aren't being stored correctly.

Even if method #7 always loaded the correct timestamp, storing the wrong timestamp in Postgres is kind of a drag. It means you can't compare that Postgres column value with the output of the Postgres `current_timestamp` function as part of a query in a meaningful way. Non-Django users of the database will simply see the wrong timestamps.

But method #7 doesn't even always load the correct timestamp in Django as the second test datetime shows. Remember we chose the second datetime to be right after a daylight savings time falll-forward event if the naive datetime is interpreted as if it were in US/Pacific. Well that's just the way Postgres does interpret it. And since that datetime in US/Pacific technically never happened, when Postgres converts it back to US/Pacific it helpfully gives us back the canonical time with the clock jumped forward an hour. Unfortunately we're interpreting that timestamp in UTC which doesn't have datetime savings time and thus we end up with a timestamp one hour later than the one we saved.

#### Methods #8 and #9

The last two methods are where we get serious. We use aware datetimes, in either UTC or US/Pacific (but any time zone would work), and we explicitly tell Postgres to return a timestamp in UTC so there are no daylight savings time issues with the naive datetime we get back. And these two methods are the only ones that store and load both test datetimes correctly. Either of these methods are a way of storing and loading correct timestamps when `settings.USE_TZ` is `False` and `TIME_ZONE` is a time zone with daylight savings time.

## Summary

Time zones are tricky! It's easy to be right most of the time but occasionally see timestamps an hour off from where they are supposed to be due to daylight savings time problems, or even more off due to implicitly choosing the wrong time zone.

The aware versus naive distinction in Python datetime objects is a great example of explicit versus implicit. This example shows that the Python mantra ["explicit is better than implicit"](http://www.python.org/dev/peps/pep-0020/) is sound advice.
