# Docker Deployment Guide

This guide covers deploying the Legal Citation Graph application using Docker containers for both local development and production deployment.

## Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Docker Compose** (included with Docker Desktop)
- At least 4GB RAM available for Docker

## Quick Start

### 1. Local Development Deployment

```bash
# Deploy development environment
./deploy.sh dev          # Linux/Mac
.\deploy.ps1 dev         # Windows PowerShell

# Or use Docker Compose directly
docker-compose -f docker-compose.dev.yml up --build -d
```

**Access URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 2. Production-like Local Deployment

```bash
# Deploy with Nginx reverse proxy
./deploy.sh local        # Linux/Mac
.\deploy.ps1 local       # Windows PowerShell

# Or use Docker Compose directly
docker-compose up --build -d
```

**Access URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Nginx Proxy: http://localhost:80

## Docker Architecture

### Service Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy  │    │   Frontend      │    │   Backend       │
│   Port 80/443  │    │   Port 3000     │    │   Port 8000     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Data Volume   │
                    │   ./data/       │
                    └─────────────────┘
```

### Container Details

#### Backend Service
- **Image**: Python 3.11-slim
- **Port**: 8000
- **Features**: 
  - FastAPI application
  - PDF processing
  - Citation parsing
  - SQLite database
  - Health checks

#### Frontend Service
- **Image**: Node.js 18-alpine
- **Port**: 3000
- **Features**:
  - Next.js application
  - React Flow graph visualization
  - Tailwind CSS styling
  - Hot reload (development)

#### Nginx Service (Production)
- **Image**: nginx:alpine
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Features**:
  - Reverse proxy
  - Load balancing
  - Rate limiting
  - Gzip compression
  - Security headers

## Deployment Options

### Development Environment

**Use Case**: Local development with hot reload
**Features**:
- Code changes trigger automatic rebuilds
- Volume mounts for live code editing
- Development dependencies included
- Debug logging enabled

```bash
docker-compose -f docker-compose.dev.yml up --build -d
```

### Production Environment

**Use Case**: Production deployment with Nginx
**Features**:
- Optimized builds
- Nginx reverse proxy
- Rate limiting and security
- Health checks and monitoring
- Production logging

```bash
docker-compose up --build -d
```

### Standalone Services

**Use Case**: Deploy individual services
**Features**:
- Independent service deployment
- Custom configuration
- Service-specific scaling

```bash
# Backend only
docker run -d -p 8000:8000 legal-citation-graph-backend:latest

# Frontend only
docker run -d -p 3000:3000 legal-citation-graph-frontend:latest
```

## Configuration

### Environment Variables

Create a `.env` file from `env.example`:

```bash
# Database
DATABASE_URL=sqlite:///./data/citations.db

# Storage
PDF_STORAGE_PATH=./data/pdfs

# API
API_PORT=8000
FRONTEND_PORT=3000

# Feature flags
FEATURE_EXTERNAL_ENRICHMENT=false
MODEL_PROVIDER=openai

# Optional: OpenAI API key
OPENAI_API_KEY=your_key_here
```

### Docker Compose Overrides

Create `docker-compose.override.yml` for custom configurations:

```yaml
version: '3.8'
services:
  backend:
    environment:
      - LOG_LEVEL=DEBUG
      - DATABASE_URL=postgresql://user:pass@db:5432/citations
    volumes:
      - ./custom-config:/app/config:ro
  
  frontend:
    environment:
      - NEXT_PUBLIC_API_URL=http://custom-api.example.com/v1
```

## Management Commands

### Using Deployment Scripts

```bash
# Linux/Mac
./deploy.sh help          # Show all commands
./deploy.sh status        # Show service status
./deploy.sh logs dev      # Show development logs
./deploy.sh stop          # Stop all services
./deploy.sh cleanup       # Clean up Docker resources

# Windows PowerShell
.\deploy.ps1 help         # Show all commands
.\deploy.ps1 status       # Show service status
.\deploy.ps1 logs dev     # Show development logs
.\deploy.ps1 stop         # Stop all services
.\deploy.ps1 cleanup      # Clean up Docker resources
```

### Using Docker Compose Directly

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Scale services
docker-compose up -d --scale backend=3

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up --build -d
```

## Production Deployment

### 1. Cloud Deployment

#### AWS ECS/Fargate
```bash
# Build and push images
docker build -t your-registry/legal-citation-graph:latest .
docker push your-registry/legal-citation-graph:latest

# Deploy with ECS
aws ecs create-service --cluster your-cluster --service-name legal-citation-graph
```

#### Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/your-project/legal-citation-graph
gcloud run deploy legal-citation-graph --image gcr.io/your-project/legal-citation-graph
```

#### Azure Container Instances
```bash
# Deploy with Azure CLI
az container create --resource-group your-rg --name legal-citation-graph --image your-registry/legal-citation-graph:latest
```

### 2. Self-Hosted Deployment

#### VPS/Server
```bash
# Clone repository
git clone https://github.com/your-repo/legal-nlp-citation-graph.git
cd legal-nlp-citation-graph

# Configure environment
cp env.example .env
# Edit .env with production values

# Deploy
./deploy.sh prod
```

#### Kubernetes
```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

## Monitoring and Maintenance

### Health Checks

```bash
# Check backend health
curl http://localhost:8000/health

# Check service status
docker-compose ps

# View resource usage
docker stats
```

### Logs and Debugging

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# View container logs
docker logs legal-citation-graph-backend
```

### Backup and Recovery

```bash
# Backup database
docker exec legal-citation-graph-backend sqlite3 /app/data/citations.db ".backup /app/data/backup.db"

# Backup uploaded files
docker exec legal-citation-graph-backend tar -czf /app/data/pdfs-backup.tar.gz /app/data/pdfs/

# Restore from backup
docker cp backup.db legal-citation-graph-backend:/app/data/citations.db
```

## Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :8000
netstat -tulpn | grep :3000

# Change ports in docker-compose.yml
ports:
  - "8001:8000"  # Map host port 8001 to container port 8000
```

#### Permission Issues
```bash
# Fix data directory permissions
sudo chown -R $USER:$USER ./data
chmod -R 755 ./data
```

#### Memory Issues
```bash
# Increase Docker memory limit
# Docker Desktop: Settings > Resources > Memory
# Linux: Edit /etc/docker/daemon.json
```

#### Build Failures
```bash
# Clean build cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
```

### Performance Optimization

#### Resource Limits
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
```

#### Caching
```yaml
services:
  frontend:
    build:
      context: ./frontend
      cache_from:
        - legal-citation-graph-frontend:cache
```

## Security Considerations

### Container Security
- Non-root user execution
- Minimal base images
- Regular security updates
- Resource limits

### Network Security
- Internal service communication
- Exposed ports only when necessary
- Reverse proxy with rate limiting
- HTTPS termination (production)

### Data Security
- Volume mounts for persistence
- Environment variable management
- No secrets in images
- Regular backups

## Scaling

### Horizontal Scaling
```bash
# Scale backend services
docker-compose up -d --scale backend=3

# Load balancer configuration
upstream backend {
    server backend:8000;
    server backend:8001;
    server backend:8002;
}
```

### Vertical Scaling
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

## Cost Optimization

### Resource Management
- Use appropriate base images
- Implement health checks
- Monitor resource usage
- Clean up unused resources

### Cloud Optimization
- Use spot instances where possible
- Implement auto-scaling
- Monitor and optimize costs
- Use reserved instances for production

## Support and Community

- **Issues**: GitHub Issues
- **Documentation**: `/cursor` directory
- **Contributing**: See CONTRIBUTING.md
- **Security**: Report to security@example.com

## License

This project follows the constraints outlined in `/cursor/product/non_goals.md` - no copyrighted content download, no hallucinated links, relies on proven legal NLP libraries.

