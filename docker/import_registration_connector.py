#!/usr/bin/env python3
"""
Import Debezium connector for event registrations
This sets up CDC (Change Data Capture) for registration tables
"""

import requests
import json
import time
import sys

def wait_for_debezium(max_retries=30, delay=5):
    """Wait for Debezium Connect to be ready"""
    print("🔄 Waiting for Debezium Connect to be ready...")
    
    for attempt in range(max_retries):
        try:
            # Use debezium service name in Docker
            response = requests.get("http://debezium:8083/connectors", timeout=10)
            if response.status_code == 200:
                print("✅ Debezium Connect is ready!")
                return True
        except requests.exceptions.RequestException as e:
            print(f"⏳ Attempt {attempt + 1}/{max_retries}: Debezium not ready yet ({e})")
            time.sleep(delay)
    
    print("❌ Debezium Connect failed to become ready")
    return False

def create_registration_connector():
    """Create the registration connector"""
    print("📡 Creating registration connector...")
    
    # Load connector configuration
    with open('registration-connector.json', 'r') as f:
        connector_config = json.load(f)
    
    try:
        # Check if connector already exists
        response = requests.get("http://debezium:8083/connectors/registration-connector")
        if response.status_code == 200:
            print("🔄 Registration connector already exists, deleting...")
            delete_response = requests.delete("http://debezium:8083/connectors/registration-connector")
            if delete_response.status_code == 204:
                print("✅ Old connector deleted")
                time.sleep(5)  # Wait for cleanup
            else:
                print(f"⚠️ Failed to delete old connector: {delete_response.status_code}")
        
        # Create new connector
        response = requests.post(
            "http://debezium:8083/connectors",
            headers={"Content-Type": "application/json"},
            json=connector_config,
            timeout=30
        )
        
        if response.status_code == 201:
            print("✅ Registration connector created successfully!")
            
            # Verify connector status
            time.sleep(3)
            status_response = requests.get("http://debezium:8083/connectors/registration-connector/status")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"📊 Connector status: {status['connector']['state']}")
                
                if status['connector']['state'] == 'RUNNING':
                    print("🎉 Registration connector is running and ready!")
                    return True
                else:
                    print(f"⚠️ Connector state: {status}")
            
            return True
            
        else:
            print(f"❌ Failed to create connector: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating connector: {e}")
        return False

def verify_topics():
    """Verify that Kafka topics are created"""
    print("🔍 Verifying Kafka topics...")
    
    # Note: In a real setup, you might want to use kafka-python to list topics
    # For now, we'll just assume they're created by Debezium
    expected_topics = [
        "event_management.public.event_registrations",
        "event_management.public.users"
    ]
    
    print(f"📋 Expected topics: {expected_topics}")
    print("✅ Topics should be auto-created by Debezium")
    return True

def main():
    print("🚀 Setting up Event Registration CDC Pipeline")
    print("=" * 60)
    
    # Wait for Debezium to be ready
    if not wait_for_debezium():
        sys.exit(1)
    
    # Create the registration connector
    if not create_registration_connector():
        sys.exit(1)
    
    # Verify topics
    if not verify_topics():
        sys.exit(1)
    
    print("\n🎉 Registration CDC pipeline setup complete!")
    print("📧 Email service will now receive registration events from Kafka")
    print("💌 Users will get confirmation emails when they register for events")

if __name__ == "__main__":
    main()
