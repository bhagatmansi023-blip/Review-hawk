# backend/check_cols.py
"""
Utility to verify that the health‑report columns were added to the
`reviews_review` table.  Run it after migrations:

    python manage.py shell < backend/check_cols.py
"""

import sys
import django

django.setup()

from django.db import connection

# ---------------------------------------------------------------------------

REQUIRED_COLS = {"health_report", "health_score", "health_grade"}

def main() -> None:
    with connection.cursor() as cursor:
        # One well‑formed SELECT statement – no duplicate SELECTs.
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'reviews_review'
            ORDER BY ordinal_position;
            """
        )
        cols = [row[0] for row in cursor.fetchall()]

    print("\n📋  Columns on `reviews_review`:", cols)

    missing = sorted(REQUIRED_COLS - set(cols))
    print("❗️  Missing columns:", missing)

    if missing:
        # Signal failure to callers (e.g. CI pipelines)
        sys.exit(1)

if __name__ == "__main__":
    main()
