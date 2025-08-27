import time
import json
from kafka import KafkaConsumer
import requests
import sys
from datetime import datetime, date, timedelta

# Logging helper
def log(msg):
    print(msg)
    sys.stdout.flush()

log("Waiting 10 seconds for Kafka to be ready...")
time.sleep(10)

KAFKA_TOPIC = "postgres.public.events"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
WEAVIATE_URL = "http://weaviate:8080/v1/objects"
WEAVIATE_CLASS = "Event"

def convert_dates(event_data):
    """Convert epoch dates and times to readable format"""
    converted_data = dict(event_data)
    
    # Convert event_date (days since epoch)
    if 'event_date' in converted_data and isinstance(converted_data['event_date'], int):
        epoch_date = datetime(1970, 1, 1) + timedelta(days=converted_data['event_date'])
        converted_data['event_date'] = epoch_date.strftime('%Y-%m-%d')
    
    # Convert event_time - appears to be milliseconds since midnight
    if 'event_time' in converted_data and isinstance(converted_data['event_time'], int):
        # Convert milliseconds to seconds first
        total_seconds = converted_data['event_time'] // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        converted_data['event_time'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Convert timestamps - appears to be milliseconds since epoch  
    for field in ['created_at', 'updated_at']:
        if field in converted_data and isinstance(converted_data[field], int):
            # Convert milliseconds to seconds for timestamp
            timestamp = datetime.fromtimestamp(converted_data[field] / 1000)
            converted_data[field] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    return converted_data

def send_to_weaviate(event_data):
    # Convert dates and keep the PostgreSQL ID as postgres_id
    event_data = convert_dates(event_data)
    postgres_id = event_data.pop('id', None)  # Remove 'id' but save it
    
    # Add postgres_id for registration functionality
    if postgres_id:
        event_data['postgres_id'] = postgres_id
    
    obj = {
        "class": WEAVIATE_CLASS,
        "properties": event_data
    }
    try:
        response = requests.post(WEAVIATE_URL, json=obj)
        log(f"Sent to Weaviate: {event_data}, Response: {response.status_code}, Body: {response.text}")
    except Exception as e:
        log(f"Error sending to Weaviate: {e}")

def main():
    log("Starting Kafka to Weaviate connector...")
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='weaviate-connector'
        )
        log("Connected to Kafka. Waiting for messages...")
    except Exception as e:
        log(f"Error connecting to Kafka: {e}")
        return
    for message in consumer:
        event = message.value
        log(f"Received message: {event}")
        if 'after' in event and event['after']:
            send_to_weaviate(event['after'])
        else:
            log("No 'after' field in message or it's null. Skipping.")

if __name__ == "__main__":
    main()
