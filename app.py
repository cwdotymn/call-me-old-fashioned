from flask import Flask, render_template, request, redirect
import csv
import os
import json
from datetime import date

app = Flask(__name__)

DATA_FILE = "data.csv"
PROFILE_FILE = "profile.json"
REGULARS_FILE = "regulars.json"
FIELDNAMES = ["visit_id", "bar_name", "location", "date", "person", "cocktail_name", "rating", "ice_quality", "taste_balance", "notes"]

def read_visits():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

def append_rows(rows):
    file_exists = os.path.exists(DATA_FILE)
    with open(DATA_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

def delete_visit_rows(visit_id):
    rows = read_visits()
    remaining = [r for r in rows if r["visit_id"] != visit_id]
    with open(DATA_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(remaining)

def known_bars():
    rows = read_visits()
    seen = []
    for r in rows:
        if r["bar_name"] and r["bar_name"] not in seen:
            seen.append(r["bar_name"])
    return seen

def group_by_visit(rows):
    visits = {}
    for row in rows:
        vid = row["visit_id"]
        if vid not in visits:
            visits[vid] = {
                "visit_id": vid,
                "bar_name": row["bar_name"],
                "location": row["location"],
                "date": row["date"],
                "cocktails": []
            }
        visits[vid]["cocktails"].append({
            "name": row["cocktail_name"],
            "person": row.get("person", ""),
            "rating": row["rating"],
            "ice_quality": row["ice_quality"],
            "taste_balance": row["taste_balance"],
            "notes": row["notes"]
        })
    return list(visits.values())

def read_profile():
    if not os.path.exists(PROFILE_FILE):
        return {"name": ""}
    with open(PROFILE_FILE, "r") as f:
        return json.load(f)

def save_profile(data):
    with open(PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def read_regulars():
    if not os.path.exists(REGULARS_FILE):
        return []
    with open(REGULARS_FILE, "r") as f:
        return json.load(f)

def save_regulars(data):
    with open(REGULARS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def build_people():
    profile = read_profile()
    regulars = read_regulars()
    return [profile["name"]] + regulars if profile["name"] else regulars

def parse_cocktail_rows(visit_id, form):
    cocktail_names = form.getlist("cocktail_name")
    persons = form.getlist("person")
    ratings = form.getlist("rating")
    ice_qualities = form.getlist("ice_quality")
    taste_balances = form.getlist("taste_balance")
    notes_list = form.getlist("notes")

    rows = []
    for i in range(len(cocktail_names)):
        if cocktail_names[i].strip():
            rows.append({
                "visit_id": visit_id,
                "bar_name": form["bar_name"],
                "location": form["location"],
                "date": form["date"],
                "person": persons[i] if i < len(persons) else "",
                "cocktail_name": cocktail_names[i],
                "rating": ratings[i],
                "ice_quality": ice_qualities[i],
                "taste_balance": taste_balances[i],
                "notes": notes_list[i]
            })
    return rows

@app.route("/")
def index():
    rows = read_visits()
    visits = group_by_visit(rows)
    visits.sort(key=lambda v: v["date"], reverse=True)
    return render_template("index.html", visits=visits)

@app.route("/add", methods=["GET", "POST"])
def add_visit():
    if request.method == "POST":
        existing = read_visits()
        visit_ids = [int(r["visit_id"]) for r in existing if r["visit_id"].isdigit()]
        visit_id = str(max(visit_ids) + 1) if visit_ids else "1"
        new_rows = parse_cocktail_rows(visit_id, request.form)
        append_rows(new_rows)
        return redirect("/")

    return render_template("add_visit.html",
        today=date.today().isoformat(),
        people=build_people(),
        bar_names=known_bars())

@app.route("/edit/<visit_id>", methods=["GET", "POST"])
def edit_visit(visit_id):
    if request.method == "POST":
        new_rows = parse_cocktail_rows(visit_id, request.form)
        delete_visit_rows(visit_id)
        append_rows(new_rows)
        return redirect("/")

    rows = read_visits()
    visit_rows = [r for r in rows if r["visit_id"] == visit_id]
    if not visit_rows:
        return redirect("/")

    visit = {
        "bar_name": visit_rows[0]["bar_name"],
        "location": visit_rows[0]["location"],
        "date": visit_rows[0]["date"],
        "cocktails": [{
            "name": r["cocktail_name"],
            "person": r.get("person", ""),
            "rating": r["rating"],
            "ice_quality": r["ice_quality"],
            "taste_balance": r["taste_balance"],
            "notes": r["notes"]
        } for r in visit_rows]
    }

    return render_template("edit_visit.html",
        visit_id=visit_id,
        visit=visit,
        people=build_people(),
        bar_names=known_bars())

@app.route("/delete/<visit_id>", methods=["POST"])
def delete_visit(visit_id):
    delete_visit_rows(visit_id)
    return redirect("/")

@app.route("/stats")
def stats():
    rows = read_visits()
    visits = group_by_visit(rows)

    total_visits = len(visits)
    total_cocktails = len(rows)

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

    top_bars = sorted(bars, key=lambda b: b["avg_rating"], reverse=True)
    most_visited = sorted(bars, key=lambda b: b["visits"], reverse=True)

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
    top_cocktails = sorted(cocktails, key=lambda c: c["avg_rating"], reverse=True)[:10]

    all_ratings = []
    for r in rows:
        try:
            all_ratings.append(int(r["rating"]))
        except (ValueError, KeyError):
            pass
    rating_dist = {i: all_ratings.count(i) for i in range(1, 6)}

    return render_template("stats.html",
        total_visits=total_visits,
        total_cocktails=total_cocktails,
        top_bars=top_bars,
        most_visited=most_visited,
        top_cocktails=top_cocktails,
        rating_dist=rating_dist)

@app.route("/manage", methods=["GET", "POST"])
def manage():
    profile = read_profile()
    regulars = read_regulars()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_profile":
            profile["name"] = request.form["profile_name"].strip()
            save_profile(profile)

        elif action == "add_regular":
            name = request.form["regular_name"].strip()
            if name and name not in regulars:
                regulars.append(name)
                save_regulars(regulars)

        elif action == "delete_regular":
            name = request.form["delete_name"]
            if name in regulars:
                regulars.remove(name)
                save_regulars(regulars)

        return redirect("/manage")

    return render_template("manage.html", profile=profile, regulars=regulars)

if __name__ == "__main__":
    app.run(debug=True)
