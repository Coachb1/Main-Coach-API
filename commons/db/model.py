import uuid

from django.db import models


class MyModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False)

    uid = models.CharField(max_length=255, default=uuid.uuid4, unique=True)

    class Meta:
        abstract = True
