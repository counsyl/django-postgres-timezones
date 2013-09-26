from django.db.models import DateTimeField
from django.db.models import Model


class Timestamp(Model):
    """
    A simple Django model for illustrating time zone issues.
    """
    timestamp = DateTimeField()
