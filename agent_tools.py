# agent_tools.py
# Utility functions (tools) that the AI agent and Streamlit app can call.
import os, subprocess
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables (MONGO_URI, DB_NAME, etc.)
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME   = os.getenv("DB_NAME", "fpl")

# Connect to MongoDB
def _db():
    return MongoClient(MONGO_URI)[DB_NAME]

# 1) Refresh the FPL data by re-running your ETL script
def refresh_data(max_players: int = 150) -> str:
    """
    Runs the ETL script to refresh the data from the FPL API.
    """
    env = os.environ.copy()
    try:
        # Run the script and capture the output
        out = subprocess.check_output(
            ["python", "etl_fpl_to_mongo.py"],
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            timeout=1800
        )
        return f"✅ Refresh completed.\n{out[-1200:]}"  # Return the last part of the output
    except subprocess.CalledProcessError as e:
        return f"❌ Refresh failed: {e.output}"
    except Exception as e:
        return f"❌ Refresh failed: {repr(e)}"

# 2) Get top xGI/90 players
def top_xgi(min_minutes: int = 300, position: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    pos_map = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}
    match = {"minutes": {"$gte": int(min_minutes)}}
    if position and position.upper() in pos_map:
        match["element_type"] = pos_map[position.upper()]
    db = _db()
    pipeline = [
        {"$match": match},
        {"$project": {
            "_id": 0,
            "id": 1,
            "web_name": 1,
            "element_type": 1,
            "minutes": 1,
            "team": 1,
            "xgi90": "$expected_goal_involvements_per_90",
            "xg90": "$expected_goals_per_90",
            "xa90": "$expected_assists_per_90",
            "price_m": {"$divide": ["$now_cost", 10]}
        }},
        {"$sort": {"xgi90": -1}},
        {"$limit": int(limit)}
    ]
    return list(db.player_snapshots.aggregate(pipeline))

# 3) Get top FPL value picks
def value_picks(min_minutes: int = 300, position: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    pos_map = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}
    match = {"minutes": {"$gte": int(min_minutes)}}
    if position and position.upper() in pos_map:
        match["element_type"] = pos_map[position.upper()]
    db = _db()
    pipeline = [
        {"$match": match},
        {"$addFields": {"price_m": {"$divide": ["$now_cost", 10]}}},
        {"$addFields": {
            "xgi90_per_m": {
                "$cond": [
                    {"$gt": ["$price_m", 0]},
                    {"$divide": ["$expected_goal_involvements_per_90", "$price_m"]},
                    None
                ]
            }
        }},
        {"$sort": {"xgi90_per_m": -1}},
        {"$limit": int(limit)},
        {"$project": {
            "_id": 0,
            "id": 1,
            "web_name": 1,
            "element_type": 1,
            "minutes": 1,
            "price_m": 1,
            "xgi90_per_m": 1
        }}
    ]
    return list(db.player_snapshots.aggregate(pipeline))

# 4) Get recent GW trend for a specific player
def recent_trend(player_name_substr: str, last_n: int = 5) -> Dict[str, Any]:
    db = _db()
    p = db.player_snapshots.find_one(
        {"web_name": {"$regex": player_name_substr, "$options": "i"}},
        {"id": 1, "web_name": 1}
    )
    if not p:
        return {"error": f"No player matches '{player_name_substr}'"}
    pid = p["id"]
    rows = list(
        db.player_history
          .find({"player_id": pid})
          .sort("round", -1)
          .limit(int(last_n))
    )
    rows = [
        {
            "round": r["round"],
            "minutes": r.get("minutes"),
            "xG": r.get("expected_goals"),
            "xA": r.get("expected_assists"),
            "xGI": r.get("expected_goal_involvements"),
            "points": r.get("total_points"),
        }
        for r in rows
    ]
    return {"player_id": pid, "web_name": p["web_name"], "recent": rows}

# 5) Suggest captain based on xGI/90 * chance of playing
def captain_suggestion(min_minutes: int = 300, limit: int = 10) -> List[Dict[str, Any]]:
    db = _db()
    pipeline = [
        {"$match": {"minutes": {"$gte": int(min_minutes)}}},
        {"$project": {
            "_id": 0,
            "id": 1,
            "web_name": 1,
            "element_type": 1,
            "minutes": 1,
            "xgi90": "$expected_goal_involvements_per_90",
            "chance": "$chance_of_playing_next_round",
            "status": 1,
            "price_m": {"$divide": ["$now_cost", 10]}
        }},
        {"$addFields": {
            "chanceF": {
                "$cond": [
                    {"$gt": ["$chance", 0]},
                    {"$divide": ["$chance", 100]},
                    0.9
                ]
            }
        }},
        {"$addFields": {"score": {"$multiply": ["$xgi90", "$chanceF"]}}},
        {"$sort": {"score": -1}},
        {"$limit": int(limit)}
    ]
    return list(db.player_snapshots.aggregate(pipeline))
