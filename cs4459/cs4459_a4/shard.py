from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27023")
admin = client["admin"]
config = client["config"]
db = client["rideflow"]

config["settings"].update_one(
    {"_id": "chunksize"},
    {"$set": {"value": 1}},
    upsert=True
)
print("Chunk size set to 1 MB")

db["trips"].create_index([("driver_id", "hashed")])
admin.command("shardCollection", "rideflow.trips", key={"driver_id": "hashed"})
print("trips sharded on driver_id (hashed)")

db["drivers"].create_index([("driver_id", "hashed")])
admin.command("shardCollection", "rideflow.drivers", key={"driver_id": "hashed"})
print("drivers sharded on driver_id (hashed)")

client.close()
print("Done — run load.py next.")