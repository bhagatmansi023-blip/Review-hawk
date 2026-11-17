from django.contrib import admin

from .models import CodeChunk, RepositoryIndex


@admin.register(RepositoryIndex)
class RepositoryIndexAdmin(admin.ModelAdmin):
    list_display = ("repository", "index_status", "indexed_files", "indexed_chunks", "indexed_at", "updated_at")
    list_filter = ("index_status",)
    search_fields = ("repository__owner", "repository__name")
    readonly_fields = ("created_at", "updated_at", "indexed_at", "index_started_at")


@admin.register(CodeChunk)
class CodeChunkAdmin(admin.ModelAdmin):
    list_display = ("repository", "file_path", "chunk_type", "symbol_name", "language", "start_line", "end_line", "created_at")
    list_filter = ("language", "chunk_type")
    search_fields = ("repository__owner", "repository__name", "file_path", "symbol_name")
    readonly_fields = ("created_at", "updated_at", "content_hash")
