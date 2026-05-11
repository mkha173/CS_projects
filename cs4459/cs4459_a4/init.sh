#!/bin/bash
set -e

echo "==> Step 1: Init config server replica set"
docker exec configsvr0 mongosh --port 27020 --eval '
rs.initiate({
  _id: "configRS",
  configsvr: true,
  members: [
    { _id: 0, host: "configsvr0:27020" },
    { _id: 1, host: "configsvr1:27021" },
    { _id: 2, host: "configsvr2:27022" }
  ]
})
'
sleep 5

echo "==> Step 2: Init shard0RS"
docker exec shard0a mongosh --port 27017 --eval '
rs.initiate({
  _id: "shard0RS",
  members: [
    { _id: 0, host: "shard0a:27017" },
    { _id: 1, host: "shard0b:27018" },
    { _id: 2, host: "shard0c:27019" }
  ]
})
'
sleep 5

echo "==> Step 3: Init shard1RS"
docker exec shard1a mongosh --port 27027 --eval '
rs.initiate({
  _id: "shard1RS",
  members: [
    { _id: 0, host: "shard1a:27027" },
    { _id: 1, host: "shard1b:27028" },
    { _id: 2, host: "shard1c:27029" }
  ]
})
'
sleep 5

echo "==> Step 4: Register shards and enable sharding"
docker exec mongos mongosh --port 27023 --eval '
sh.addShard("shard0RS/shard0a:27017,shard0b:27018,shard0c:27019");
sh.addShard("shard1RS/shard1a:27027,shard1b:27028,shard1c:27029");
sh.enableSharding("rideflow");
'

echo "Done."