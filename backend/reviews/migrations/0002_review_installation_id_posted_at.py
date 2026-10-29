"""
reviews/migrations/0002_review_installation_id_posted_at.py
============================================================
Adds installation_id and posted_at to the Review model.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="installation_id",
            field=models.BigIntegerField(
                blank=True,
                null=True,
                help_text="GitHub App installation ID from the webhook payload. "
                          "Used to authenticate as the App when posting reviews.",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="posted_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Timestamp when the review was successfully posted to GitHub.",
            ),
        ),
        migrations.AddField(
            model_name='review',
            name='health_details',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='health_grade',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='review',
            name='health_score',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='risk_level',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
