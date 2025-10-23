# agent.py
# Chat-style agent that uses OpenAI function-calling to run tools in agent_tools.py

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import agent_tools as tools

# Load env vars (OPENAI_API_KEY, etc.)
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = """You are a football FPL data agent.
You can call tools to fetch data from a MongoDB-backed FPL dataset.
Be concise and format answers as short bullet points or compact table-like text.

Tools available:
- refresh_data(max_players=150): refresh FPL data into MongoDB.
- top_xgi(min_minutes=300, position=None, limit=10): top players by xGI/90.
- value_picks(min_minutes=300, position=None, limit=10): xGI/90 per £m.
- recent_trend(player_name_substr, last_n=5): last GWs for a player.
- captain_suggestion(min_minutes=300, limit=10): captain options based on availability × xGI/90.

If no tool is needed, just answer directly. Otherwise, call the tool(s) and summarize results clearly.
"""

# OpenAI tool schema (function calling)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "refresh_data",
            "description": "Refresh data from FPL API into MongoDB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_players": {"type": "integer", "default": 150}
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_xgi",
            "description": "Top players by xGI per 90 minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_minutes": {"type": "integer", "default": 300},
                    "position": {"type": "string", "enum": ["GK", "DEF", "MID", "FWD"]},
                    "limit": {"type": "integer", "default": 10}
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "value_picks",
            "description": "Top value players by xGI/90 per £ million.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_minutes": {"type": "integer", "default": 300},
                    "position": {"type": "string", "enum": ["GK", "DEF", "MID", "FWD"]},
                    "limit": {"type": "integer", "default": 10}
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_trend",
            "description": "Recent gameweek stats for a player by rough name match.",
            "parameters": {
                "type": "object",
                "required": ["player_name_substr"],
                "properties": {
                    "player_name_substr": {"type": "string"},
                    "last_n": {"type": "integer", "default": 5}
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "captain_suggestion",
            "description": "Suggest captain options using xGI/90 and availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_minutes": {"type": "integer", "default": 300},
                    "limit": {"type": "integer", "default": 10}
                }
            },
        },
    },
]

def call_tool(name: str, args: dict):
    """Dispatch to local tool functions."""
    if name == "refresh_data":
        return tools.refresh_data(**args)
    if name == "top_xgi":
        return tools.top_xgi(**args)
    if name == "value_picks":
        return tools.value_picks(**args)
    if name == "recent_trend":
        return tools.recent_trend(**args)
    if name == "captain_suggestion":
        return tools.captain_suggestion(**args)
    return {"error": f"Unknown tool '{name}'"}

def chat_once(user_text: str) -> str:
    """One-shot chat turn with correct tool-calling protocol."""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text},
    ]

    # 1) Let the model decide whether to call a tool
    first = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=memo(messages),
        tools=TOOLS,
        tool_choice="auto",
        temperature=0,
    )
    assistant_msg = first.choices[0].message

    # 2) If tools requested, append exactly ONE assistant message with tool_calls
    if assistant_msg.tool_calls:
        # Normalize tool_calls to raw dicts
        tool_calls = []
        for tc in assistant_msg.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            })

        messages.append({
            "role": "assistant",
            "content": assistant_msg.content or "",
            "tool_calls": tool_calls,
        })

        # 3) Execute each tool and append ONE tool message with matching tool_call_id and name
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            args_json = tc["function"]["arguments"] or "{}"
            try:
                args = json.loads(args_json)
            except Exception:
                args = {}
            result = call_tool(func_name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": func_name,                  # REQUIRED
                "content": json.dumps(result),      # string content
            })

        # 4) Ask model to summarize tool outputs
        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=memo(messages),
            temperature=0,
        )
        return final.choices[0].message.content

    # 5) No tools needed
    return assistant_msg.content

def memo(msgs):
    """(Optional) shallow copy helper to avoid accidental mutation."""
    return [dict(m) for m in msgs]

if __name__ == "__main__":
    print("Type a question (e.g., 'Who should I captain?'). Type 'exit' to quit.")
    while True:
        try:
            q = input("> ").strip()
        except EOFError:
            break
        if not q or q.lower() in {"exit", "quit"}:
            break
        print(chat_once(q))
