import os, requests, datetime
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME   = os.getenv("DB_NAME", "fpl")

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FIXTURES_URL  = "https://fantasy.premierleague.com/api/fixtures/"
SUMMARY_URL   = "https://fantasy.premierleague.com/api/element-summary/{player_id}/"

def mongo():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def ensure_indexes(db):
    db.players.create_index([("id", ASCENDING)], unique=True)
    db.teams.create_index([("id", ASCENDING)], unique=True)
    db.events.create_index([("id", ASCENDING)], unique=True)
    db.player_history.create_index([("player_id", ASCENDING), ("round", ASCENDING)], unique=True)
    db.player_snapshots.create_index([("id", ASCENDING)], unique=True)

def fetch_json(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def load_bootstrap(db):
    j = fetch_json(BOOTSTRAP_URL)
    players, teams, events = j["elements"], j["teams"], j["events"]

    for p in players:
        p["_ingestedAt"] = datetime.datetime.utcnow()
        db.player_snapshots.update_one({"id": p["id"]}, {"$set": p}, upsert=True)

    for t in teams:
        db.teams.update_one({"id": t["id"]}, {"$set": t}, upsert=True)
    for e in events:
        db.events.update_one({"id": e["id"]}, {"$set": e}, upsert=True)

    print(f"Loaded players={len(players)}, teams={len(teams)}, events={len(events)}")

def load_player_history(db, max_players=150):
    players = list(db.player_snapshots.find({}, {"id":1, "minutes":1}).sort("minutes", -1).limit(max_players))
    count = 0
    for p in players:
        pid = p["id"]
        j = fetch_json(SUMMARY_URL.format(player_id=pid))
        for row in j.get("history", []):
            row["player_id"] = pid
            db.player_history.update_one(
                {"player_id": pid, "round": row["round"]},
                {"$set": row},
                upsert=True
            )
        count += 1
    print(f"Loaded per-GW history for {count} players")

def load_fixtures(db):
    fixtures = fetch_json(FIXTURES_URL)
    db.fixtures.drop()
    if fixtures:
        db.fixtures.insert_many(fixtures)
    print(f"Loaded fixtures={len(fixtures)}")

if __name__ == "__main__":
    db = mongo()
    ensure_indexes(db)
    load_bootstrap(db)
    load_player_history(db, max_players=150)
    load_fixtures(db)
    print("Done.")
