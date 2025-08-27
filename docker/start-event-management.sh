#!/bin/bash
# start-event-management.sh - One-command startup for the entire system

set -e

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Print banner
echo -e "${GREEN}"
cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                    Event Management System                   ║
║                     🚀 Starting All Services                ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    error "docker-compose is not installed. Please install it first."
    exit 1
fi

# Navigate to docker directory
log "Navigating to docker directory..."
cd "$(dirname "$0")"

# Stop any existing containers
log "Stopping any existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true

# Remove old volumes if requested
if [[ "${1}" == "--fresh" ]]; then
    warning "Fresh start requested - removing all volumes..."
    docker-compose down -v 2>/dev/null || true
    docker volume prune -f 2>/dev/null || true
fi

# Pull latest images
log "Pulling latest Docker images..."
docker-compose pull --quiet

# Build custom images
log "Building custom application images..."
docker-compose build --no-cache

# Start infrastructure services first
log "Starting infrastructure services (PostgreSQL, Kafka, Weaviate)..."
docker-compose up -d postgres zookeeper kafka schema-registry weaviate debezium

# Wait a bit for infrastructure to stabilize
log "Waiting for infrastructure to stabilize..."
sleep 15

# Start initialization services
log "Starting initialization services..."
docker-compose up -d master_init

# Wait for initialization to complete
log "Waiting for system initialization to complete..."
sleep 30

# Start application services
log "Starting application services..."
docker-compose up -d backend frontend frontend-ss frontend-ss2 email_service

# Show service status
log "Checking service status..."
sleep 10

echo -e "\n${GREEN}🎉 Event Management System is starting up!${NC}"
echo -e "\n📋 Service Status:"
docker-compose ps

echo -e "\n🌐 Access URLs:"
echo -e "  • Main Frontend:     ${BLUE}http://localhost:8501${NC}"
echo -e "  • Chatbot SS:        ${BLUE}http://localhost:8502${NC}"
echo -e "  • Chatbot SS2:       ${BLUE}http://localhost:8503${NC}"
echo -e "  • Backend API:       ${BLUE}http://localhost:8000${NC}"
echo -e "  • PostgreSQL:        ${BLUE}localhost:5445${NC}"
echo -e "  • Weaviate:          ${BLUE}http://localhost:8080${NC}"

echo -e "\n📊 Health Checks:"
echo -e "  • Database Health:   ${BLUE}http://localhost:8000/health${NC}"
echo -e "  • Weaviate Ready:    ${BLUE}http://localhost:8080/v1/.well-known/ready${NC}"

echo -e "\n📝 Logs:"
echo -e "  • View all logs:     ${YELLOW}docker-compose logs -f${NC}"
echo -e "  • View service logs: ${YELLOW}docker-compose logs -f [service-name]${NC}"

echo -e "\n🛑 Stop System:"
echo -e "  • Stop all:          ${YELLOW}docker-compose down${NC}"
echo -e "  • Stop with volumes: ${YELLOW}docker-compose down -v${NC}"

success "Event Management System startup initiated!"
warning "Services may take a few more minutes to fully initialize."
log "Monitor logs with: docker-compose logs -f"
