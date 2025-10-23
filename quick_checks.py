import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME","fpl")]

pipeline = [
  {"$match": {"minutes": {"$gte": 300}}},
  {"$project": {"_id":0, "id":1, "web_name":1, "element_type":1,
                "minutes":1, "xgi90":"$expected_goal_involvements_per_90"}},
  {"$sort": {"xgi90": -1}},
  {"$limit": 10}
]
print("Top xGI/90 (min 300 mins):")
for r in db.player_snapshots.aggregate(pipeline):
    print(r)

any_player = db.player_snapshots.find_one({}, {"id":1, "web_name":1})
pid, name = any_player["id"], any_player["web_name"]
recent = list(db.player_history.find({"player_id": pid}).sort("round", -1).limit(5))
print(f"\nRecent 5 GWs for {name} (player_id={pid}):")
for r in recent:
    print({"round": r["round"], "minutes": r["minutes"],
           "xG": r.get("expected_goals"), "xA": r.get("expected_assists"),
           "xGI": r.get("expected_goal_involvements")})

client.close()
