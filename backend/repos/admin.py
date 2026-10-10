from django.contrib import admin

from .models import PullRequest, Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "is_enabled", "is_private", "created_at")
    list_filter = ("is_enabled", "is_private")
    search_fields = ("owner", "name")


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ("repository", "number", "title", "author", "state", "updated_at")
    list_filter = ("state",)
    search_fields = ("title", "author")

