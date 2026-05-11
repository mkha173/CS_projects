# =============================================================
# CS 4459 — Assignment 4: Data Loader
# PROVIDED — do not modify, do not submit.
#
# Run order:
#   1. docker compose up -d
#   2. bash init.sh
#   3. python shard.py
#   4. python load.py          ← this script
# =============================================================
# Install dependencies: pip install pymongo

import json
from datetime import datetime
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27023/")
db = client["rideflow"]

def parse_dates(doc, fields):
    for f in fields:
        if f in doc:
            doc[f] = datetime.fromisoformat(doc[f])
    return doc

# --- Load trips ---
print("Loading trips...")
with open("trips.json") as f:
    trips = json.load(f)

trips = [parse_dates(t, ["start_time", "end_time"]) for t in trips]

BATCH = 500
for i in range(0, len(trips), BATCH):
    db.trips.insert_many(trips[i:i + BATCH])

# --- Load drivers ---
print("Loading drivers...")
with open("drivers.json") as f:
    drivers = json.load(f)

for i in range(0, len(drivers), BATCH):
    db.drivers.insert_many(drivers[i:i + BATCH])

# --- Summary ---
print(f"\nLoad complete.")
print(f"  trips:   {db.trips.count_documents({})}")
print(f"  drivers: {db.drivers.count_documents({})}")
print("\nWait ~60s for the balancer, then verify:")
print("  docker exec mongos mongosh --port 27023 --eval 'sh.status()'")