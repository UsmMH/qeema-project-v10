#!/usr/bin/env python3
"""
Event Registration Email Service
Kafka consumer that sends registration confirmation emails
"""

import os
import json
import logging
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import psycopg2
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailService:
    """Handles email sending via SMTP"""
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.from_name = os.getenv('FROM_NAME', 'Event Management System')
        
        logger.info(f"Email service configured for {self.smtp_host}:{self.smtp_port}")
    
    def send_registration_confirmation(self, user_email: str, user_name: str, event_details: Dict) -> bool:
        """Send registration confirmation email"""
        try:
            # Create email content
            subject = f"✅ Registration Confirmed: {event_details['title']}"
            
            # HTML email template
            html_body = self._create_email_template(user_name, event_details)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = user_email
            
            # Add HTML part
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Registration email sent to {user_email} for event {event_details['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {user_email}: {e}")
            return False
    
    def _create_email_template(self, user_name: str, event_details: Dict) -> str:
        """Create professional HTML email template"""
        event_date = event_details.get('event_date', 'TBD')
        event_time = event_details.get('event_time', 'TBD')
        
        if event_date != 'TBD' and event_time != 'TBD':
            formatted_datetime = f"{event_date} at {event_time}"
        elif event_date != 'TBD':
            formatted_datetime = event_date
        else:
            formatted_datetime = "Date and time to be announced"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Event Registration Confirmation</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">🎉 Registration Confirmed!</h1>
            </div>
            
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <p style="font-size: 18px; margin-bottom: 20px;">Hello <strong>{user_name}</strong>,</p>
                
                <p style="margin-bottom: 20px;">Great news! Your registration for the following event has been confirmed:</p>
                
                <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; margin: 20px 0;">
                    <h2 style="color: #667eea; margin-top: 0; margin-bottom: 15px;">{event_details['title']}</h2>
                    
                    <div style="margin-bottom: 10px;">
                        <strong>📅 Date & Time:</strong> {formatted_datetime}
                    </div>
                    
                    <div style="margin-bottom: 10px;">
                        <strong>📍 Location:</strong> {event_details.get('location', 'Location TBD')}
                    </div>
                    
                    <div style="margin-bottom: 10px;">
                        <strong>🏷️ Category:</strong> {event_details.get('category', 'General')}
                    </div>
                    
                    <div style="margin-bottom: 10px;">
                        <strong>👤 Organizer:</strong> {event_details.get('organizer', 'Event Organizer')}
                    </div>
                    
                    {f'<div style="margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 5px;"><strong>Description:</strong><br>{event_details["description"]}</div>' if event_details.get('description') else ''}
                </div>
                
                <div style="background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px;">
                        <strong>📝 Important Notes:</strong><br>
                        • Please arrive 15 minutes early<br>
                        • Bring a valid ID if required<br>
                        • Check your email for any updates<br>
                        • Contact the organizer if you need to cancel
                    </p>
                </div>
                
                <p style="margin-top: 30px;">We're excited to see you at the event!</p>
                
                <p style="margin-bottom: 0;">Best regards,<br>
                <strong>Event Management Team</strong></p>
            </div>
            
            <div style="text-align: center; padding: 20px; font-size: 12px; color: #666;">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>© 2025 Event Management System. All rights reserved.</p>
            </div>
        </body>
        </html>
        """

class DatabaseService:
    """Handles database operations"""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5445')
        self.database = os.getenv('DB_NAME', 'event_management')
        self.user = os.getenv('DB_USER', 'eventuser')
        self.password = os.getenv('DB_PASSWORD', 'eventpass123')
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )
    
    def mark_email_sent(self, registration_id: int) -> bool:
        """Mark email as sent in database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE event_registrations 
                        SET email_sent = TRUE, email_sent_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (registration_id,))
                    conn.commit()
            logger.info(f"Marked email as sent for registration {registration_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark email as sent: {e}")
            return False
    
    def get_registration_details(self, registration_id: int) -> Optional[Dict]:
        """Get complete registration details"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM registration_details 
                        WHERE registration_id = %s
                    """, (registration_id,))
                    
                    row = cur.fetchone()
                    if row:
                        columns = [desc[0] for desc in cur.description]
                        return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"Failed to get registration details: {e}")
            return None

class RegistrationEmailConsumer:
    """Main Kafka consumer for registration events"""
    
    def __init__(self):
        self.kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = 'event_management.public.event_registrations'
        self.group_id = 'email-service-group'
        
        self.email_service = EmailService()
        self.db_service = DatabaseService()
        
        logger.info("Registration email consumer initialized")
    
    def connect_kafka(self) -> KafkaConsumer:
        """Connect to Kafka with retry logic"""
        max_retries = 10
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.kafka_bootstrap_servers,
                    group_id=self.group_id,
                    value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None,
                    auto_offset_reset='earliest',  # Process all messages from the beginning
                    enable_auto_commit=True
                )
                logger.info(f"Connected to Kafka at {self.kafka_bootstrap_servers}")
                return consumer
                
            except NoBrokersAvailable as e:
                logger.warning(f"Kafka not available (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
    
    def process_registration_event(self, message: Dict) -> None:
        """Process a registration event from Kafka"""
        try:
            # Handle raw table data format (after Debezium unwrap transform)
            after_data = message
            if not after_data:
                logger.warning("No data in message")
                return
            
            registration_id = after_data.get('id')
            status = after_data.get('status', '')
            email_sent = after_data.get('email_sent', False)
            
            # Only process registered status and if email not already sent
            if status != 'registered' or email_sent:
                logger.debug(f"Skipping registration {registration_id}: status={status}, email_sent={email_sent}")
                return
            
            logger.info(f"Processing new registration {registration_id}")
            
            # Get complete registration details
            registration_details = self.db_service.get_registration_details(registration_id)
            if not registration_details:
                logger.error(f"Could not fetch details for registration {registration_id}")
                return
            
            # Prepare event details for email
            event_details = {
                'title': registration_details['event_title'],
                'description': registration_details['event_description'],
                'category': registration_details['event_category'],
                'location': registration_details['event_location'],
                'event_date': str(registration_details['event_date']) if registration_details['event_date'] else 'TBD',
                'event_time': str(registration_details['event_time']) if registration_details['event_time'] else 'TBD',
                'organizer': registration_details['organizer']
            }
            
            # Send confirmation email
            user_email = registration_details['email']
            user_name = registration_details['full_name'] or registration_details['username']
            
            if self.email_service.send_registration_confirmation(user_email, user_name, event_details):
                # Mark email as sent in database
                self.db_service.mark_email_sent(registration_id)
                logger.info(f"Successfully processed registration {registration_id}")
            else:
                logger.error(f"Failed to send email for registration {registration_id}")
                
        except Exception as e:
            logger.error(f"Error processing registration event: {e}")
    
    def run(self):
        """Main consumer loop"""
        logger.info("Starting registration email service...")
        
        consumer = self.connect_kafka()
        
        try:
            logger.info(f"Listening for messages on topic: {self.topic}")
            
            for message in consumer:
                try:
                    if message.value:
                        self.process_registration_event(message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
                    
        except KeyboardInterrupt:
            logger.info("Shutting down email service...")
        finally:
            consumer.close()

def main():
    """Main entry point"""
    logger.info("🚀 Event Registration Email Service Starting...")
    
    # Validate environment variables
    required_env_vars = ['SMTP_USER', 'SMTP_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return
    
    # Start the consumer
    consumer = RegistrationEmailConsumer()
    consumer.run()

if __name__ == "__main__":
    main()
