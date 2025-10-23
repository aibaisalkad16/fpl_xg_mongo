# app.py — FPL xG Mongo + AI Agent UI
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Local tools you already created
import agent_tools as tools
from agent import chat_once  # uses your OpenAI key and tool-calling

load_dotenv()

st.set_page_config(page_title="FPL xG – AI", page_icon="⚽", layout="wide")

# --- Sidebar ---
st.sidebar.title("⚙️ Controls")

with st.sidebar.expander("Filters", expanded=True):
    min_minutes = st.number_input("Min minutes", min_value=0, value=300, step=50)
    position = st.selectbox("Position", ["Any", "GK", "DEF", "MID", "FWD"])
    limit = st.slider("Rows to show", min_value=5, max_value=50, value=15)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh FPL data"):
    with st.status("Refreshing data from FPL API…", expanded=True) as status:
        out = tools.refresh_data()
        st.write(out)
        status.update(label="Refresh complete", state="complete", expanded=False)

st.sidebar.markdown("---")
st.sidebar.caption("ENV check")
st.sidebar.write("Mongo URI set:", bool(os.getenv("MONGO_URI")))
st.sidebar.write("OpenAI key set:", bool(os.getenv("OPENAI_API_KEY")))

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Captain picks", "📈 xGI Leaders", "💸 Value picks", "💬 Ask the Agent"])

# --- Captain picks ---
with tab1:
    st.subheader("Suggested Captain Options")
    data = tools.captain_suggestion(min_minutes=min_minutes, limit=limit)
    if not data:
        st.info("No data yet — try refreshing.")
    else:
        df = pd.DataFrame(data)
        # Pretty columns
        col_map = {
            "web_name": "Player",
            "element_type": "Pos",
            "minutes": "Minutes",
            "xgi90": "xGI/90",
            "chance": "Chance next GW",
            "status": "Status",
            "price_m": "£m",
            "score": "Score"
        }
        df = df.rename(columns=col_map)
        # Translate numeric position
        pos_map = {1:"GK",2:"DEF",3:"MID",4:"FWD"}
        if "Pos" in df.columns:
            df["Pos"] = df["Pos"].map(pos_map).fillna(df["Pos"])
        st.dataframe(df[[c for c in ["Player","Pos","Minutes","xGI/90","Chance next GW","Status","£m","Score"] if c in df.columns]])

# --- xGI Leaders ---
with tab2:
    st.subheader("xGI per 90 — Leaders")
    pos = None if position == "Any" else position
    data = tools.top_xgi(min_minutes=min_minutes, position=pos, limit=limit)
    if not data:
        st.info("No data yet — try refreshing.")
    else:
        df = pd.DataFrame(data)
        pos_map = {1:"GK",2:"DEF",3:"MID",4:"FWD"}
        if "element_type" in df.columns:
            df["Pos"] = df["element_type"].map(pos_map)
        df["£m"] = df["price_m"]
        show_cols = ["web_name","Pos","minutes","xgi90","xg90","xa90","£m"]
        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[show_cols].rename(columns={
            "web_name":"Player","minutes":"Minutes","xgi90":"xGI/90","xg90":"xG/90","xa90":"xA/90"
        }))

# --- Value picks ---
with tab3:
    st.subheader("Value Picks — xGI/90 per £m")
    pos = None if position == "Any" else position
    data = tools.value_picks(min_minutes=min_minutes, position=pos, limit=limit)
    if not data:
        st.info("No data yet — try refreshing.")
    else:
        df = pd.DataFrame(data)
        pos_map = {1:"GK",2:"DEF",3:"MID",4:"FWD"}
        if "element_type" in df.columns:
            df["Pos"] = df["element_type"].map(pos_map)
        df["£m"] = df["price_m"]
        show_cols = ["web_name","Pos","minutes","£m","xgi90_per_m"]
        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[show_cols].rename(columns={
            "web_name":"Player","minutes":"Minutes","xgi90_per_m":"xGI/90 per £m"
        }))

# --- Chat agent ---
with tab4:
    st.subheader("Ask the Agent")
    st.caption("Examples: 'Who should I captain?', 'Top 10 mids by xGI/90', 'Show Haaland trend', 'Refresh the data'")
    q = st.text_input("Your question")
    if st.button("Ask"):
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Missing OPENAI_API_KEY in environment or .env")
        else:
            with st.spinner("Thinking…"):
                ans = chat_once(q)
            st.write(ans)
