#!/bin/bash

# Event Registration System Setup Script
# This script sets up the database schema and starts the services

set -e

echo "🚀 Setting up Event Registration System"
echo "============================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Please edit .env file with your email credentials!"
    echo "   Required: SMTP_USER and SMTP_PASSWORD"
    echo ""
fi

# Apply database schema
echo " Applying database schema..."
export PGPASSWORD=eventpass123
psql -h localhost -p 5445 -U eventuser -d event_management -f registration_schema.sql

if [ $? -eq 0 ]; then
    echo " Database schema applied successfully!"
else
    echo " Failed to apply database schema"
    echo "Please ensure PostgreSQL is running on localhost:5445"
    exit 1
fi

echo ""
echo "🎉 Setup completed!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your email credentials"
echo "2. Start the services: docker-compose up -d email_service"
echo "3. Set up registration connector: python import_registration_connector.py"
echo ""
echo " Email service will automatically send confirmation emails when users register!"
