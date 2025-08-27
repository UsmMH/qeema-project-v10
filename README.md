# Event Management System

A fully automated, containerized platform for managing events, registrations, and notifications with AI-powered recommendations and real-time email alerts.

## Features
- Event creation, browsing, and registration
- AI-powered event recommendations (OpenAI integration)
- Real-time notifications via email
- Modern, interactive frontend (Streamlit)
- FastAPI backend API
- PostgreSQL database with sample data
- Kafka & Debezium for real-time data streaming
- Weaviate vector search for semantic event discovery
- Fully automated Docker Compose deployment

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url](https://github.com/MOAZHAGGAG/qeemaass>
   cd qeemaass-dev/docker
   ```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in your OpenAI and email credentials.

3. **Start the system:**
   ```bash
   ./start-event-management.sh
   # or
   docker-compose up --build
   ```

4. **Access the applications:**
   - Main Frontend: [http://localhost:8501](http://localhost:8501)
   - Chatbot SS: [http://localhost:8502](http://localhost:8502)
   - Chatbot SS2: [http://localhost:8503](http://localhost:8503)
   - Backend API: [http://localhost:8000](http://localhost:8000)

## Architecture
- **Frontend:** Streamlit apps for user interaction and chatbots
- **Backend:** FastAPI for business logic and API
- **Database:** PostgreSQL with automated schema and sample data
- **Messaging:** Kafka + Debezium for CDC and notifications
- **Search:** Weaviate for semantic event search
- **Email:** Automated notifications for registrations

## Automation
- All services, connectors, and schema setup are fully automated.
- No manual steps required—just run the startup script or `docker-compose up`.
- Registration connector and all initialization scripts are included in the build.

## Requirements
- Docker & Docker Compose
- OpenAI API key (for AI features)
- SMTP credentials (for email notifications)

