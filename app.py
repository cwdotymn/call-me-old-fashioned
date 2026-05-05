from flask import Flask, render_template, request, redirect, g
import sqlite3
import os
from datetime import date

app = Flask(__name__)
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmof.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_FILE) as db:
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


init_db()


def build_people():
    db = get_db()
    profile = db.execute("SELECT name FROM profile WHERE id = 1").fetchone()
    regulars = [r["name"] for r in db.execute("SELECT name FROM regulars ORDER BY name").fetchall()]
    name = profile["name"] if profile else ""
    return [name] + regulars if name else regulars


def known_bars():
    db = get_db()
    return [r["bar_name"] for r in db.execute("SELECT DISTINCT bar_name FROM visits ORDER BY bar_name").fetchall()]


def get_visits():
    db = get_db()
    visits = db.execute("SELECT * FROM visits ORDER BY date DESC").fetchall()
    result = []
    for v in visits:
        cocktails = db.execute("SELECT * FROM cocktails WHERE visit_id = ?", (v["id"],)).fetchall()
        result.append({
            "visit_id": str(v["id"]),
            "bar_name": v["bar_name"],
            "location": v["location"],
            "date": v["date"],
            "cocktails": [{
                "name": c["cocktail_name"],
                "person": c["person"],
                "rating": str(c["rating"]),
                "ice_quality": c["ice_quality"],
                "taste_balance": str(c["taste_balance"]),
                "notes": c["notes"]
            } for c in cocktails]
        })
    return result


def parse_cocktail_dicts(form):
    cocktail_names = form.getlist("cocktail_name")
    persons = form.getlist("person")
    ratings = form.getlist("rating")
    ice_qualities = form.getlist("ice_quality")
    taste_balances = form.getlist("taste_balance")
    notes_list = form.getlist("notes")

    cocktails = []
    for i in range(len(cocktail_names)):
        if cocktail_names[i].strip():
            cocktails.append({
                "person": persons[i] if i < len(persons) else "",
                "cocktail_name": cocktail_names[i],
                "rating": ratings[i],
                "ice_quality": ice_qualities[i],
                "taste_balance": taste_balances[i],
                "notes": notes_list[i]
            })
    return cocktails


def insert_visit(bar_name, location, visit_date, cocktails):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO visits (bar_name, location, date) VALUES (?, ?, ?)",
        (bar_name, location, visit_date)
    )
    visit_id = cursor.lastrowid
    for c in cocktails:
        db.execute(
            "INSERT INTO cocktails (visit_id, person, cocktail_name, rating, ice_quality, taste_balance, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (visit_id, c["person"], c["cocktail_name"], c["rating"], c["ice_quality"], c["taste_balance"], c["notes"])
        )
    db.commit()


def update_visit(visit_id, bar_name, location, visit_date, cocktails):
    db = get_db()
    db.execute("UPDATE visits SET bar_name=?, location=?, date=? WHERE id=?",
               (bar_name, location, visit_date, visit_id))
    db.execute("DELETE FROM cocktails WHERE visit_id=?", (visit_id,))
    for c in cocktails:
        db.execute(
            "INSERT INTO cocktails (visit_id, person, cocktail_name, rating, ice_quality, taste_balance, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (visit_id, c["person"], c["cocktail_name"], c["rating"], c["ice_quality"], c["taste_balance"], c["notes"])
        )
    db.commit()


@app.route("/")
def index():
    return render_template("index.html", visits=get_visits())


@app.route("/add", methods=["GET", "POST"])
def add_visit():
    if request.method == "POST":
        insert_visit(
            request.form["bar_name"],
            request.form["location"],
            request.form["date"],
            parse_cocktail_dicts(request.form)
        )
        return redirect("/")
    return render_template("add_visit.html",
        today=date.today().isoformat(),
        people=build_people(),
        bar_names=known_bars())


@app.route("/edit/<int:visit_id>", methods=["GET", "POST"])
def edit_visit(visit_id):
    db = get_db()
    if request.method == "POST":
        update_visit(visit_id, request.form["bar_name"], request.form["location"],
                     request.form["date"], parse_cocktail_dicts(request.form))
        return redirect("/")

    v = db.execute("SELECT * FROM visits WHERE id=?", (visit_id,)).fetchone()
    if not v:
        return redirect("/")
    cocktail_rows = db.execute("SELECT * FROM cocktails WHERE visit_id=?", (visit_id,)).fetchall()
    visit = {
        "bar_name": v["bar_name"],
        "location": v["location"],
        "date": v["date"],
        "cocktails": [{
            "name": c["cocktail_name"],
            "person": c["person"],
            "rating": str(c["rating"]),
            "ice_quality": c["ice_quality"],
            "taste_balance": str(c["taste_balance"]),
            "notes": c["notes"]
        } for c in cocktail_rows]
    }
    return render_template("edit_visit.html",
        visit_id=visit_id,
        visit=visit,
        people=build_people(),
        bar_names=known_bars())


@app.route("/delete/<int:visit_id>", methods=["POST"])
def delete_visit(visit_id):
    db = get_db()
    db.execute("DELETE FROM cocktails WHERE visit_id=?", (visit_id,))
    db.execute("DELETE FROM visits WHERE id=?", (visit_id,))
    db.commit()
    return redirect("/")


@app.route("/stats")
def stats():
    visits = get_visits()
    total_visits = len(visits)
    total_cocktails = sum(len(v["cocktails"]) for v in visits)

    bar_data = {}
    for v in visits:
        name = v["bar_name"]
        if name not in bar_data:
            bar_data[name] = {"visits": 0, "ratings": []}
        bar_data[name]["visits"] += 1
        for c in v["cocktails"]:
            try:
                bar_data[name]["ratings"].append(float(c["rating"]))
            except (ValueError, KeyError):
                pass

    bars = []
    for name, d in bar_data.items():
        avg = sum(d["ratings"]) / len(d["ratings"]) if d["ratings"] else 0
        bars.append({"name": name, "visits": d["visits"], "avg_rating": round(avg, 1)})

    cocktail_data = {}
    for v in visits:
        for c in v["cocktails"]:
            name = c["name"]
            if not name:
                continue
            if name not in cocktail_data:
                cocktail_data[name] = {"count": 0, "ratings": []}
            cocktail_data[name]["count"] += 1
            try:
                cocktail_data[name]["ratings"].append(float(c["rating"]))
            except (ValueError, KeyError):
                pass

    cocktails = []
    for name, d in cocktail_data.items():
        avg = sum(d["ratings"]) / len(d["ratings"]) if d["ratings"] else 0
        cocktails.append({"name": name, "count": d["count"], "avg_rating": round(avg, 1)})

    all_ratings = []
    for v in visits:
        for c in v["cocktails"]:
            try:
                all_ratings.append(int(c["rating"]))
            except (ValueError, KeyError):
                pass

    return render_template("stats.html",
        total_visits=total_visits,
        total_cocktails=total_cocktails,
        top_bars=sorted(bars, key=lambda b: b["avg_rating"], reverse=True),
        most_visited=sorted(bars, key=lambda b: b["visits"], reverse=True),
        top_cocktails=sorted(cocktails, key=lambda c: c["avg_rating"], reverse=True)[:10],
        rating_dist={i: all_ratings.count(i) for i in range(1, 6)})


@app.route("/manage", methods=["GET", "POST"])
def manage():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save_profile":
            db.execute("UPDATE profile SET name=? WHERE id=1", (request.form["profile_name"].strip(),))
            db.commit()
        elif action == "add_regular":
            name = request.form["regular_name"].strip()
            if name:
                try:
                    db.execute("INSERT INTO regulars (name) VALUES (?)", (name,))
                    db.commit()
                except sqlite3.IntegrityError:
                    pass
        elif action == "delete_regular":
            db.execute("DELETE FROM regulars WHERE name=?", (request.form["delete_name"],))
            db.commit()
        return redirect("/manage")

    profile = db.execute("SELECT name FROM profile WHERE id=1").fetchone()
    regulars = [r["name"] for r in db.execute("SELECT name FROM regulars ORDER BY name").fetchall()]
    return render_template("manage.html",
        profile={"name": profile["name"] if profile else ""},
        regulars=regulars)


if __name__ == "__main__":
    app.run(debug=True)
