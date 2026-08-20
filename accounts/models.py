from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    institution = models.CharField(
        max_length=255,
        blank=True,
        help_text="Your university or organization (optional).",
    )
