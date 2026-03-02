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

@app.route("/")
def index():
    rows = read_visits()
    visits = group_by_visit(rows)
    visits.sort(key=lambda v: v["date"], reverse=True)
    return render_template("index.html", visits=visits)

@app.route("/add", methods=["GET", "POST"])
def add_visit():
    profile = read_profile()
    regulars = read_regulars()
    people = [profile["name"]] + regulars if profile["name"] else regulars

    if request.method == "POST":
        bar_name = request.form["bar_name"]
        location = request.form["location"]
        visit_date = request.form["date"]

        # Add any new regulars submitted on the fly
        new_regular = request.form.get("new_regular", "").strip()
        if new_regular and new_regular not in regulars:
            regulars.append(new_regular)
            save_regulars(regulars)

        existing = read_visits()
        visit_ids = [int(r["visit_id"]) for r in existing if r["visit_id"].isdigit()]
        visit_id = str(max(visit_ids) + 1) if visit_ids else "1"

        cocktail_names = request.form.getlist("cocktail_name")
        persons = request.form.getlist("person")
        ratings = request.form.getlist("rating")
        ice_qualities = request.form.getlist("ice_quality")
        taste_balances = request.form.getlist("taste_balance")
        notes_list = request.form.getlist("notes")

        new_rows = []
        for i in range(len(cocktail_names)):
            if cocktail_names[i].strip():
                new_rows.append({
                    "visit_id": visit_id,
                    "bar_name": bar_name,
                    "location": location,
                    "date": visit_date,
                    "person": persons[i] if i < len(persons) else "",
                    "cocktail_name": cocktail_names[i],
                    "rating": ratings[i],
                    "ice_quality": ice_qualities[i],
                    "taste_balance": taste_balances[i],
                    "notes": notes_list[i]
                })

        append_rows(new_rows)
        return redirect("/")

    return render_template("add_visit.html", today=date.today().isoformat(), people=people)

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