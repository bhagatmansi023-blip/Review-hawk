from django.contrib import admin

from .models import Review, ReviewComment, WebhookEvent


class ReviewCommentInline(admin.TabularInline):
    model = ReviewComment
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("pull_request", "head_sha", "status", "files_reviewed", "created_at")
    list_filter = ("status",)
    inlines = [ReviewCommentInline]


@admin.register(ReviewComment)
class ReviewCommentAdmin(admin.ModelAdmin):
    list_display = ("file_path", "line_number", "severity", "category", "source", "posted")
    list_filter = ("severity", "category", "source", "posted")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "action", "repository", "processed", "received_at")
    list_filter = ("event_type", "action", "processed")

