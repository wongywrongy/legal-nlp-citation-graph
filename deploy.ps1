# Legal Citation Graph Deployment Script for Windows
# This script helps deploy the application to different environments

param(
    [Parameter(Position=0)]
    [ValidateSet("local", "dev", "prod", "build", "stop", "logs", "status", "cleanup", "help")]
    [string]$Command = "help"
)

# Configuration
$ProjectName = "legal-citation-graph"
$ImageTag = "latest"

# Functions
function Write-Header {
    Write-Host "=================================" -ForegroundColor Blue
    Write-Host "  Legal Citation Graph Deploy   " -ForegroundColor Blue
    Write-Host "=================================" -ForegroundColor Blue
}

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-Docker {
    try {
        $null = docker --version
        $null = docker-compose --version
        Write-Success "Docker and Docker Compose are available"
        return $true
    }
    catch {
        Write-Error "Docker is not installed or not in PATH. Please install Docker Desktop first."
        return $false
    }
}

function Build-Images {
    Write-Step "Building Docker images..."
    
    try {
        # Build backend
        docker build -t ${ProjectName}-backend:${ImageTag} .
        
        # Build frontend
        docker build -t ${ProjectName}-frontend:${ImageTag} ./frontend
        
        Write-Success "Images built successfully"
    }
    catch {
        Write-Error "Failed to build images: $_"
        exit 1
    }
}

function Deploy-Local {
    Write-Step "Deploying locally with Docker Compose..."
    
    try {
        # Stop existing containers
        docker-compose down --remove-orphans
        
        # Build and start services
        docker-compose up --build -d
        
        Write-Success "Local deployment completed!"
        Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
        Write-Host "Backend API: http://localhost:8000" -ForegroundColor Green
        Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
        Write-Host "Nginx: http://localhost:80" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to deploy locally: $_"
        exit 1
    }
}

function Deploy-Dev {
    Write-Step "Deploying development environment..."
    
    try {
        # Stop existing containers
        docker-compose -f docker-compose.dev.yml down --remove-orphans
        
        # Build and start development services
        docker-compose -f docker-compose.dev.yml up --build -d
        
        Write-Success "Development deployment completed!"
        Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
        Write-Host "Backend API: http://localhost:8000" -ForegroundColor Green
        Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to deploy development: $_"
        exit 1
    }
}

function Deploy-Production {
    Write-Step "Deploying production environment..."
    
    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        Write-Error ".env file not found. Please create one from env.example"
        exit 1
    }
    
    try {
        # Stop existing containers
        docker-compose down --remove-orphans
        
        # Build and start production services
        docker-compose up --build -d
        
        Write-Success "Production deployment completed!"
        Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
        Write-Host "Backend API: http://localhost:8000" -ForegroundColor Green
        Write-Host "Nginx: http://localhost:80" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to deploy production: $_"
        exit 1
    }
}

function Stop-Services {
    Write-Step "Stopping all services..."
    
    try {
        # Stop all containers
        docker-compose down --remove-orphans
        docker-compose -f docker-compose.dev.yml down --remove-orphans
        
        Write-Success "All services stopped"
    }
    catch {
        Write-Error "Failed to stop services: $_"
    }
}

function Show-Logs {
    param([string]$Environment = "")
    
    Write-Step "Showing logs..."
    
    try {
        if ($Environment -eq "dev") {
            docker-compose -f docker-compose.dev.yml logs -f
        }
        else {
            docker-compose logs -f
        }
    }
    catch {
        Write-Error "Failed to show logs: $_"
    }
}

function Show-Status {
    Write-Step "Service status:"
    
    try {
        Write-Host "`nProduction Services:" -ForegroundColor Blue
        docker-compose ps
        
        Write-Host "`nDevelopment Services:" -ForegroundColor Blue
        docker-compose -f docker-compose.dev.yml ps
        
        Write-Host "`nAll Containers:" -ForegroundColor Blue
        docker ps --filter "name=${ProjectName}"
    }
    catch {
        Write-Error "Failed to show status: $_"
    }
}

function Cleanup-Docker {
    Write-Step "Cleaning up Docker resources..."
    
    try {
        # Remove stopped containers
        docker container prune -f
        
        # Remove unused images
        docker image prune -f
        
        # Remove unused volumes
        docker volume prune -f
        
        # Remove unused networks
        docker network prune -f
        
        Write-Success "Cleanup completed"
    }
    catch {
        Write-Error "Failed to cleanup: $_"
    }
}

function Show-Help {
    Write-Host "Usage: .\deploy.ps1 {local|dev|prod|build|stop|logs|status|cleanup|help}" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor White
    Write-Host "  local     - Deploy locally with production setup" -ForegroundColor White
    Write-Host "  dev       - Deploy development environment" -ForegroundColor White
    Write-Host "  prod      - Deploy production environment" -ForegroundColor White
    Write-Host "  build     - Build Docker images only" -ForegroundColor White
    Write-Host "  stop      - Stop all services" -ForegroundColor White
    Write-Host "  logs      - Show logs (use 'logs dev' for development)" -ForegroundColor White
    Write-Host "  status    - Show service status" -ForegroundColor White
    Write-Host "  cleanup   - Clean up Docker resources" -ForegroundColor White
    Write-Host "  help      - Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor White
    Write-Host "  .\deploy.ps1 local          # Deploy locally" -ForegroundColor White
    Write-Host "  .\deploy.ps1 dev            # Deploy development" -ForegroundColor White
    Write-Host "  .\deploy.ps1 logs dev       # Show development logs" -ForegroundColor White
    Write-Host "  .\deploy.ps1 status         # Show all service status" -ForegroundColor White
}

# Main script
function Main {
    Write-Header
    
    switch ($Command) {
        "local" {
            if (Test-Docker) {
                Deploy-Local
            }
        }
        "dev" {
            if (Test-Docker) {
                Deploy-Dev
            }
        }
        "prod" {
            if (Test-Docker) {
                Deploy-Production
            }
        }
        "build" {
            if (Test-Docker) {
                Build-Images
            }
        }
        "stop" {
            Stop-Services
        }
        "logs" {
            Show-Logs
        }
        "status" {
            Show-Status
        }
        "cleanup" {
            Cleanup-Docker
        }
        "help" {
            Show-Help
        }
        default {
            Write-Error "Unknown command: $Command"
            Write-Host "Use '.\deploy.ps1 help' for usage information" -ForegroundColor White
            exit 1
        }
    }
}

# Run main function
Main

