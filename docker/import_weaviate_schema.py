import requests
import json
import time

WEAVIATE_URL = "http://weaviate:8080/v1/schema"
SCHEMA_PATH = "weaviate_schema.json"

# Wait for Weaviate to be up
for _ in range(30):
    try:
        r = requests.get(WEAVIATE_URL)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(2)
else:
    print("Weaviate did not start in time.")
    exit(1)

# Check if schema is already imported
r = requests.get(WEAVIATE_URL)
if r.status_code == 200 and r.json().get("classes"):
    print("Schema already exists.")
    exit(0)

# Import schema
with open(SCHEMA_PATH) as f:
    schema = json.load(f)

r = requests.post(WEAVIATE_URL, json=schema)
if r.status_code == 200:
    print("Schema imported successfully.")
else:
    print(f"Failed to import schema: {r.text}")
    exit(1)
