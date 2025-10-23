import os, certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGO_URI")
print("URI scheme:", uri.split("://",1)[0])   # should print mongodb+srv

client = MongoClient(uri, serverSelectionTimeoutMS=20000, tlsCAFile=certifi.where())
try:
    print("Ping:", client.admin.command("ping"))
    print("✅ Connected OK")
except Exception as e:
    print("❌ Connection failed:", e)
