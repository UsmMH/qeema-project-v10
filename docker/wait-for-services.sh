#!/bin/bash
# wait-for-services.sh - Comprehensive service startup coordination

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
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

# Wait for PostgreSQL
wait_for_postgres() {
    log "Waiting for PostgreSQL to be ready..."
    until pg_isready -h postgres -p 5432 -U eventuser; do
        log "PostgreSQL is unavailable - sleeping"
        sleep 2
    done
    success "PostgreSQL is ready!"
}

# Wait for Kafka
wait_for_kafka() {
    log "Waiting for Kafka to be ready..."
    for i in {1..30}; do
        if kafka-topics --bootstrap-server kafka:9092 --list >/dev/null 2>&1; then
            success "Kafka is ready!"
            return 0
        fi
        log "Kafka is unavailable - sleeping"
        sleep 2
    done
    error "Kafka failed to start"
    return 1
}

# Wait for Weaviate
wait_for_weaviate() {
    log "Waiting for Weaviate to be ready..."
    for i in {1..30}; do
        if curl -f http://weaviate:8080/v1/.well-known/ready >/dev/null 2>&1; then
            success "Weaviate is ready!"
            return 0
        fi
        log "Weaviate is unavailable - sleeping"
        sleep 2
    done
    error "Weaviate failed to start"
    return 1
}

# Wait for Debezium Connect
wait_for_debezium() {
    log "Waiting for Debezium Connect to be ready..."
    for i in {1..30}; do
        if curl -f http://debezium:8083/connectors >/dev/null 2>&1; then
            success "Debezium Connect is ready!"
            return 0
        fi
        log "Debezium Connect is unavailable - sleeping"
        sleep 2
    done
    error "Debezium Connect failed to start"
    return 1
}

# Main execution
main() {
    log "🚀 Starting service dependency checks..."
    
    case "${1:-all}" in
        postgres)
            wait_for_postgres
            ;;
        kafka)
            wait_for_kafka
            ;;
        weaviate)
            wait_for_weaviate
            ;;
        debezium)
            wait_for_debezium
            ;;
        all)
            wait_for_postgres
            wait_for_kafka
            wait_for_weaviate
            wait_for_debezium
            ;;
        *)
            error "Unknown service: $1"
            error "Usage: $0 [postgres|kafka|weaviate|debezium|all]"
            exit 1
            ;;
    esac
    
    success "All requested services are ready!"
}

main "$@"
