"""
One-time migration: imports data.csv, profile.json, and regulars.json into cmof.db.
Run once on PythonAnywhere after deploying the updated app:

    python migrate.py
"""
import csv
import json
import os
import sqlite3

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmof.db")


def init_db(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bar_name TEXT NOT NULL,
            location TEXT DEFAULT '',
            date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cocktails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL,
            person TEXT DEFAULT '',
            cocktail_name TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            ice_quality TEXT DEFAULT '',
            taste_balance INTEGER DEFAULT 5,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT DEFAULT ''
        );
        INSERT OR IGNORE INTO profile (id, name) VALUES (1, '');
        CREATE TABLE IF NOT EXISTS regulars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
    """)


def migrate():
    base = os.path.dirname(os.path.abspath(__file__))
    db = sqlite3.connect(DB_FILE)
    init_db(db)

    # Visits and cocktails
    data_file = os.path.join(base, "data.csv")
    if os.path.exists(data_file):
        visits = {}
        with open(data_file, newline="") as f:
            for row in csv.DictReader(f):
                vid = row["visit_id"]
                if vid not in visits:
                    visits[vid] = {
                        "bar_name": row["bar_name"],
                        "location": row["location"],
                        "date": row["date"],
                        "cocktails": []
                    }
                visits[vid]["cocktails"].append({
                    "person": row.get("person", ""),
                    "cocktail_name": row["cocktail_name"],
                    "rating": row["rating"],
                    "ice_quality": row["ice_quality"],
                    "taste_balance": row["taste_balance"],
                    "notes": row["notes"]
                })

        for vid, v in sorted(visits.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            cursor = db.execute(
                "INSERT INTO visits (bar_name, location, date) VALUES (?, ?, ?)",
                (v["bar_name"], v["location"], v["date"])
            )
            new_vid = cursor.lastrowid
            for c in v["cocktails"]:
                db.execute(
                    "INSERT INTO cocktails (visit_id, person, cocktail_name, rating, ice_quality, taste_balance, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (new_vid, c["person"], c["cocktail_name"], c["rating"],
                     c["ice_quality"], c["taste_balance"], c["notes"])
                )
        print(f"Migrated {len(visits)} visit(s) from data.csv")
    else:
        print("No data.csv found, skipping")

    # Profile
    profile_file = os.path.join(base, "profile.json")
    if os.path.exists(profile_file):
        with open(profile_file) as f:
            profile = json.load(f)
        db.execute("UPDATE profile SET name=? WHERE id=1", (profile.get("name", ""),))
        print(f"Migrated profile: {profile.get('name', '(empty)')}")
    else:
        print("No profile.json found, skipping")

    # Regulars
    regulars_file = os.path.join(base, "regulars.json")
    if os.path.exists(regulars_file):
        with open(regulars_file) as f:
            regulars = json.load(f)
        for name in regulars:
            db.execute("INSERT OR IGNORE INTO regulars (name) VALUES (?)", (name,))
        print(f"Migrated {len(regulars)} regular(s) from regulars.json")
    else:
        print("No regulars.json found, skipping")

    db.commit()
    db.close()
    print("Done. cmof.db is ready.")


if __name__ == "__main__":
    migrate()
