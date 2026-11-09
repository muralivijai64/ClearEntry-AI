
from pathlib import Path
from sqlalchemy import text
from app.database import engine

upload_dir = Path("uploads").resolve()

print("\nUPLOAD DIRECTORY:")
print(upload_dir)

print("\nFILES CURRENTLY PRESENT:")
for file in upload_dir.iterdir():
    print(file.name)

print("\nDATABASE DOCUMENT RECORDS:")

with engine.connect() as connection:
    rows = connection.execute(
        text("""
            SELECT id, original_filename, stored_filename
            FROM documents
        """)
    ).fetchall()

    for row in rows:
        stored_path = upload_dir / row.stored_filename

        print("\nDocument ID:", row.id)
        print("Original filename:", row.original_filename)
        print("Stored filename:", row.stored_filename)
        print("Expected file path:", stored_path)
        print("File exists:", stored_path.exists())
