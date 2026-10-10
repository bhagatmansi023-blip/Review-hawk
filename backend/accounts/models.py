
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class User(AbstractUser):
    """Custom user. Must exist before the first migration (AUTH_USER_MODEL)."""

    # Filled in after GitHub login (django-allauth stores the raw account
    # separately; these are convenient copies for the dashboard).
    github_username = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True)

    def __str__(self):
        return self.github_username or self.username