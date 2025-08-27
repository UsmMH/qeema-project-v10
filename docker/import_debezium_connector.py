import requests
import time
import json

CONNECTOR_CONFIG_PATH = "postgres-connector.json"
DEBEZIUM_URL = "http://debezium:8083/connectors"

# Wait for Debezium to be up
for _ in range(30):
    try:
        r = requests.get(DEBEZIUM_URL.replace("/connectors", ""))
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(2)
else:
    print("Debezium did not start in time.")
    exit(1)

# Check if connector already exists
r = requests.get(DEBEZIUM_URL)
if r.status_code == 200 and "postgres-connector" in r.text:
    print("Connector already exists.")
    exit(0)

# Post connector config
with open(CONNECTOR_CONFIG_PATH) as f:
    config = json.load(f)

r = requests.post(DEBEZIUM_URL, json=config)
if r.status_code in [200, 201]:
    print("Connector created successfully.")
else:
    print(f"Failed to create connector: {r.text}")
    exit(1)
