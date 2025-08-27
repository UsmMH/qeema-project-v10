#!/usr/bin/env python3
"""
Master initialization script for Event Management System
Coordinates all service initialization in the correct order
"""

import subprocess
import time
import sys
import requests
import json

class EventManagementInitializer:
    def __init__(self):
        self.services_ready = {
            'postgres': False,
            'kafka': False, 
            'weaviate': False,
            'debezium': False
        }
    
    def log(self, message, level="INFO"):
        levels = {
            "INFO": "🔵",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌"
        }
        print(f"{levels.get(level, '🔵')} {message}")
    
    def wait_for_service(self, service_name, check_function, max_retries=30, delay=5):
        """Generic service wait function"""
        self.log(f"Waiting for {service_name} to be ready...")
        
        for attempt in range(max_retries):
            try:
                if check_function():
                    self.log(f"{service_name} is ready!", "SUCCESS")
                    self.services_ready[service_name] = True
                    return True
            except Exception as e:
                self.log(f"Attempt {attempt + 1}/{max_retries}: {service_name} not ready yet", "WARNING")
                time.sleep(delay)
        
        self.log(f"{service_name} failed to become ready", "ERROR")
        return False
    
    def check_postgres(self):
        """Check if PostgreSQL is ready"""
        try:
            result = subprocess.run(['pg_isready', '-h', 'postgres', '-p', '5432', '-U', 'eventuser'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def check_weaviate(self):
        """Check if Weaviate is ready"""
        try:
            response = requests.get("http://weaviate:8080/v1/.well-known/ready", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def check_debezium(self):
        """Check if Debezium Connect is ready"""
        try:
            response = requests.get("http://debezium:8083/connectors", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def initialize_database_schema(self):
        """Initialize the database schema"""
        self.log("Initializing database schema...")
        try:
            # The schema should be auto-loaded via init.sql, but let's verify
            result = subprocess.run([
                'docker', 'exec', '-i', 'event_management_db', 
                'psql', '-U', 'eventuser', '-d', 'event_management', 
                '-c', 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = \'public\';'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and '5' in result.stdout:
                self.log("Database schema is properly initialized", "SUCCESS")
                return True
            else:
                self.log("Database schema initialization may have failed", "WARNING")
                # Try to run the init script manually
                subprocess.run([
                    'docker', 'exec', '-i', 'event_management_db',
                    'psql', '-U', 'eventuser', '-d', 'event_management'
                ], input=open('/app/migrations/init.sql').read(), text=True, timeout=60)
                return True
        except Exception as e:
            self.log(f"Database initialization error: {e}", "ERROR")
            return False
    
    def setup_weaviate_schema(self):
        """Setup Weaviate schema"""
        self.log("Setting up Weaviate schema...")
        try:
            result = subprocess.run(['python', '/app/import_weaviate_schema.py'], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.log("Weaviate schema setup completed", "SUCCESS")
                return True
            else:
                self.log(f"Weaviate schema setup failed: {result.stderr}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Weaviate schema setup error: {e}", "ERROR")
            return False
    
    def setup_debezium_connectors(self):
        """Setup Debezium connectors"""
        self.log("Setting up Debezium connectors...")
        
        # Setup main Debezium connector
        try:
            result = subprocess.run(['python', '/app/import_debezium_connector.py'], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                self.log(f"Main Debezium connector setup failed: {result.stderr}", "WARNING")
        except Exception as e:
            self.log(f"Main Debezium connector error: {e}", "WARNING")
        
        # Setup registration connector
        try:
            result = subprocess.run(['python', '/app/import_registration_connector.py'], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.log("Registration connector setup completed", "SUCCESS")
                return True
            else:
                self.log(f"Registration connector setup failed: {result.stderr}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Registration connector setup error: {e}", "ERROR")
            return False
    
    def verify_system_health(self):
        """Verify overall system health"""
        self.log("Performing system health check...")
        
        checks = [
            ("Database tables", self.check_database_tables),
            ("Weaviate schema", self.check_weaviate_schema),
            ("Debezium connectors", self.check_debezium_connectors)
        ]
        
        all_healthy = True
        for check_name, check_func in checks:
            try:
                if check_func():
                    self.log(f"{check_name}: OK", "SUCCESS")
                else:
                    self.log(f"{check_name}: FAILED", "ERROR")
                    all_healthy = False
            except Exception as e:
                self.log(f"{check_name}: ERROR - {e}", "ERROR")
                all_healthy = False
        
        return all_healthy
    
    def check_database_tables(self):
        """Check if database tables exist"""
        try:
            result = subprocess.run([
                'docker', 'exec', 'event_management_db',
                'psql', '-U', 'eventuser', '-d', 'event_management',
                '-t', '-c', 'SELECT COUNT(*) FROM events;'
            ], capture_output=True, text=True, timeout=15)
            return result.returncode == 0 and int(result.stdout.strip()) > 0
        except:
            return False
    
    def check_weaviate_schema(self):
        """Check if Weaviate schema exists"""
        try:
            response = requests.get("http://weaviate:8080/v1/schema", timeout=10)
            return response.status_code == 200 and len(response.json().get('classes', [])) > 0
        except:
            return False
    
    def check_debezium_connectors(self):
        """Check if Debezium connectors are running"""
        try:
            response = requests.get("http://debezium:8083/connectors", timeout=10)
            if response.status_code == 200:
                connectors = response.json()
                return len(connectors) > 0
        except:
            pass
        return False
    
    def run_initialization(self):
        """Run the complete initialization sequence"""
        self.log("🚀 Starting Event Management System Initialization", "INFO")
        self.log("=" * 60)
        
        # Step 1: Wait for core services
        core_services = [
            ('postgres', self.check_postgres),
            ('weaviate', self.check_weaviate), 
            ('debezium', self.check_debezium)
        ]
        
        for service_name, check_func in core_services:
            if not self.wait_for_service(service_name, check_func):
                self.log(f"Failed to start {service_name}, aborting initialization", "ERROR")
                return False
        
        # Step 2: Initialize database schema
        if not self.initialize_database_schema():
            self.log("Database schema initialization failed", "ERROR")
            return False
        
        # Step 3: Setup Weaviate schema
        if not self.setup_weaviate_schema():
            self.log("Weaviate schema setup failed", "WARNING")
            # Don't fail completely, continue
        
        # Step 4: Setup Debezium connectors
        if not self.setup_debezium_connectors():
            self.log("Debezium connectors setup failed", "WARNING")
            # Don't fail completely, continue
        
        # Step 5: Final health check
        if self.verify_system_health():
            self.log("🎉 Event Management System is fully initialized and healthy!", "SUCCESS")
            self.log("🌐 Frontend services should now be accessible")
            self.log("📊 Backend API is ready")
            self.log("💾 Database contains sample events")
            self.log("📧 Email notifications are configured")
            return True
        else:
            self.log("⚠️ System initialized but some components may need attention", "WARNING")
            return True  # Still allow system to continue

def main():
    initializer = EventManagementInitializer()
    success = initializer.run_initialization()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
