import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()
from django.db import connection
cursor = connection.cursor()

for table in ['repos_pullrequest', 'reviews_review', 'reviews_reviewcomment']:
    cursor.execute(f"SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")
    print(f"\n=== {table} ===")
    for r in cursor.fetchall():
        print(f"  {r[0]:35} {r[1]:25} nullable={r[2]} default={str(r[3])[:30]}")
