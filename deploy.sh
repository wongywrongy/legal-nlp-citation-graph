#!/bin/bash

# Legal Citation Graph Deployment Script
# This script helps deploy the application to different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="legal-citation-graph"
DOCKER_REGISTRY=""
IMAGE_TAG="latest"

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Legal Citation Graph Deploy  ${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are available"
}

build_images() {
    print_step "Building Docker images..."
    
    # Build backend
    docker build -t ${PROJECT_NAME}-backend:${IMAGE_TAG} .
    
    # Build frontend
    docker build -t ${PROJECT_NAME}-frontend:${IMAGE_TAG} ./frontend
    
    print_success "Images built successfully"
}

deploy_local() {
    print_step "Deploying locally with Docker Compose..."
    
    # Stop existing containers
    docker-compose down --remove-orphans
    
    # Build and start services
    docker-compose up --build -d
    
    print_success "Local deployment completed!"
    echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
    echo -e "${GREEN}Backend API:${NC} http://localhost:8000"
    echo -e "${GREEN}API Docs:${NC} http://localhost:8000/docs"
    echo -e "${GREEN}Nginx:${NC} http://localhost:80"
}

deploy_dev() {
    print_step "Deploying development environment..."
    
    # Stop existing containers
    docker-compose -f docker-compose.dev.yml down --remove-orphans
    
    # Build and start development services
    docker-compose -f docker-compose.dev.yml up --build -d
    
    print_success "Development deployment completed!"
    echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
    echo -e "${GREEN}Backend API:${NC} http://localhost:8000"
    echo -e "${GREEN}API Docs:${NC} http://localhost:8000/docs"
}

deploy_production() {
    print_step "Deploying production environment..."
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        print_error ".env file not found. Please create one from env.example"
        exit 1
    fi
    
    # Stop existing containers
    docker-compose down --remove-orphans
    
    # Build and start production services
    docker-compose up --build -d
    
    print_success "Production deployment completed!"
    echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
    echo -e "${GREEN}Backend API:${NC} http://localhost:8000"
    echo -e "${GREEN}Nginx:${NC} http://localhost:80"
}

stop_services() {
    print_step "Stopping all services..."
    
    # Stop all containers
    docker-compose down --remove-orphans
    docker-compose -f docker-compose.dev.yml down --remove-orphans
    
    print_success "All services stopped"
}

show_logs() {
    print_step "Showing logs..."
    
    if [ "$1" = "dev" ]; then
        docker-compose -f docker-compose.dev.yml logs -f
    else
        docker-compose logs -f
    fi
}

show_status() {
    print_step "Service status:"
    
    echo -e "\n${BLUE}Production Services:${NC}"
    docker-compose ps
    
    echo -e "\n${BLUE}Development Services:${NC}"
    docker-compose -f docker-compose.dev.yml ps
    
    echo -e "\n${BLUE}All Containers:${NC}"
    docker ps --filter "name=${PROJECT_NAME}"
}

cleanup() {
    print_step "Cleaning up Docker resources..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    # Remove unused networks
    docker network prune -f
    
    print_success "Cleanup completed"
}

# Main script
main() {
    print_header
    
    case "$1" in
        "local")
            check_docker
            deploy_local
            ;;
        "dev")
            check_docker
            deploy_dev
            ;;
        "prod"|"production")
            check_docker
            deploy_production
            ;;
        "build")
            check_docker
            build_images
            ;;
        "stop")
            stop_services
            ;;
        "logs")
            show_logs "$2"
            ;;
        "status")
            show_status
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"--help"|"-h"|"")
            echo "Usage: $0 {local|dev|prod|build|stop|logs|status|cleanup|help}"
            echo ""
            echo "Commands:"
            echo "  local     - Deploy locally with production setup"
            echo "  dev       - Deploy development environment"
            echo "  prod      - Deploy production environment"
            echo "  build     - Build Docker images only"
            echo "  stop      - Stop all services"
            echo "  logs      - Show logs (use 'logs dev' for development)"
            echo "  status    - Show service status"
            echo "  cleanup   - Clean up Docker resources"
            echo "  help      - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 local          # Deploy locally"
            echo "  $0 dev            # Deploy development"
            echo "  $0 logs dev       # Show development logs"
            echo "  $0 status         # Show all service status"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"

