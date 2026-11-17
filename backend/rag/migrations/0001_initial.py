import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("repos", "0005_repository_html_url_alter_pullrequest_html_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepositoryIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "repository",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="index",
                        to="repos.repository",
                    ),
                ),
                (
                    "index_status",
                    models.CharField(
                        choices=[
                            ("never", "Never Indexed"),
                            ("pending", "Pending"),
                            ("indexing", "Indexing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="never",
                        max_length=20,
                    ),
                ),
                ("indexed_commit_sha", models.CharField(blank=True, default="", max_length=40)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                ("indexed_files", models.IntegerField(default=0)),
                ("indexed_chunks", models.IntegerField(default=0)),
                ("index_error", models.TextField(blank=True, default="")),
                ("index_started_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="CodeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "repository",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="code_chunks",
                        to="repos.repository",
                    ),
                ),
                ("file_path", models.CharField(max_length=500)),
                ("language", models.CharField(max_length=50)),
                (
                    "chunk_type",
                    models.CharField(
                        choices=[
                            ("function", "Function"),
                            ("class", "Class"),
                            ("method", "Method"),
                            ("module", "Module"),
                            ("documentation", "Documentation"),
                            ("config", "Config"),
                            ("block", "Block"),
                        ],
                        default="block",
                        max_length=20,
                    ),
                ),
                ("symbol_name", models.CharField(blank=True, default="", max_length=200)),
                ("content", models.TextField()),
                ("content_hash", models.CharField(max_length=64)),
                ("start_line", models.IntegerField()),
                ("end_line", models.IntegerField()),
                ("commit_sha", models.CharField(max_length=40)),
                ("embedding", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="codechunk",
            index=models.Index(fields=["repository", "file_path"], name="rag_chunk_repo_path_idx"),
        ),
        migrations.AddIndex(
            model_name="codechunk",
            index=models.Index(fields=["repository", "chunk_type"], name="rag_chunk_repo_type_idx"),
        ),
        migrations.AddIndex(
            model_name="codechunk",
            index=models.Index(fields=["content_hash"], name="rag_chunk_hash_idx"),
        ),
    ]
