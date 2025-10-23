import os, numpy as np, pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import Ridge

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME","fpl")]

rows = []
cursor = db.player_history.aggregate([{"$sort": {"player_id":1, "round":1}}])
per_player = {}
for h in cursor:
    pid = h["player_id"]
    per_player.setdefault(pid, []).append(h)

for pid, hist in per_player.items():
    hist = sorted(hist, key=lambda r: r["round"])
    for i in range(len(hist)-1):
        prev4 = hist[max(0, i-3):i+1]
        mean_xgi = np.mean([r.get("expected_goal_involvements", 0) for r in prev4])
        mean_mins = np.mean([r.get("minutes", 0) for r in prev4])
        next_points = hist[i+1].get("total_points")
        if next_points is None: continue
        rows.append({"player_id": pid, "round": hist[i]["round"],
                     "xgi_l4": mean_xgi, "mins_l4": mean_mins,
                     "points_next": next_points})

train_hist = pd.DataFrame(rows)
if train_hist.empty:
    raise SystemExit("Not enough history — rerun ETL or raise max_players.")

snap_cols = ["id","element_type","now_cost","minutes",
             "expected_goals_per_90","expected_assists_per_90",
             "expected_goal_involvements_per_90",
             "chance_of_playing_next_round","status"]
snap = pd.DataFrame(list(db.player_snapshots.find({}, {c:1 for c in snap_cols})))
train = train_hist.merge(snap, left_on="player_id", right_on="id", how="left")

y = train["points_next"].values
X = train[["xgi_l4","mins_l4",
           "expected_goal_involvements_per_90","expected_goals_per_90","expected_assists_per_90",
           "now_cost","element_type","status","chance_of_playing_next_round"]]

num = ["xgi_l4","mins_l4","expected_goal_involvements_per_90","expected_goals_per_90",
       "expected_assists_per_90","now_cost","chance_of_playing_next_round"]
cat = ["element_type","status"]

ct = ColumnTransformer([("num", StandardScaler(), num),
                        ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42)
Xtr_t = ct.fit_transform(Xtr); Xte_t = ct.transform(Xte)
model = Ridge(alpha=1.0).fit(Xtr_t, ytr)
print("Model R^2 (test):", model.score(Xte_t, yte))

pred_all = snap.copy()
pred_all["xgi_l4"] = pred_all["expected_goal_involvements_per_90"].fillna(0)
pred_all["mins_l4"] = np.minimum(90, pred_all["minutes"].fillna(0)/10.0)
pred_X = pred_all[["xgi_l4","mins_l4",
                   "expected_goal_involvements_per_90","expected_goals_per_90","expected_assists_per_90",
                   "now_cost","element_type","status","chance_of_playing_next_round"]]
pred_all["pred_next_points"] = model.predict(ct.transform(pred_X))
print(pred_all.sort_values("pred_next_points", ascending=False)
      [["id","element_type","now_cost","pred_next_points"]].head(20))
client.close()
