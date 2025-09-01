# Legal Citation Graph

An AI-assisted legal citation graph system that uses proven libraries for citation extraction and normalization, with optional CourtListener integration for enhanced resolution.

## System Overview

The Legal Citation Graph provides a comprehensive solution for processing legal documents, extracting citations, and visualizing citation relationships. The system follows a deterministic-first approach, using AI only for resolving ambiguous citation matches.

## Core Features

- **Document Processing**: Automated PDF upload and text extraction with precise character positioning
- **Citation Extraction**: Intelligent parsing and normalization of legal citations
- **Graph Visualization**: Interactive network visualization of citation relationships
- **Document Management**: Comprehensive browsing and analysis of processed documents
- **Deterministic Pipeline**: Rule-based processing with AI assistance for edge cases

## Quick Start

### Docker Deployment (Recommended)

The system is containerized for consistent deployment across environments.

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build -d

# Start production environment
docker-compose up --build -d

# Use deployment scripts
./deploy.sh local          # Linux/Mac
.\deploy.ps1 local         # Windows PowerShell
```

**Service Endpoints:**
- Frontend Application: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Local Development Setup

#### Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher (frontend development)
- Docker Desktop (for containerized deployment)

#### Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the backend server
python start_backend.py
```

The API server will be available at `http://localhost:8000`

#### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Health Check System

The system includes a comprehensive health check mechanism to verify all components are functioning correctly.

### Running Health Checks

#### Quick Health Check

```bash
# Run the comprehensive health check script
python health_check.py
```

This script performs the following verifications:
- File structure validation
- Docker container status
- Backend API health
- API endpoint accessibility
- Frontend service availability

#### Test Suite Execution

```bash
# Run the complete test suite
python run_test_suite.py

# Run specific test categories
python run_test_suite.py --category

# Run tests with specific markers
python run_test_suite.py --marker unit

# Run full suite with detailed reporting
python run_test_suite.py --full
```

#### Individual Test Categories

```bash
# Health check tests
pytest tests/test_health.py -v

# API endpoint tests
pytest tests/test_api_endpoints.py -v

# Database model tests
pytest tests/test_models.py -v

# Citation parser tests
pytest tests/test_citation_parser.py -v

# Integration tests
pytest tests/test_integration.py -v

# Frontend component tests
pytest tests/test_frontend_components.py -v
```

### Health Check Output

The health check system provides clear, professional status indicators:

- `[PASS]` - Component is functioning correctly
- `[FAIL]` - Component has critical issues
- `[WARN]` - Component has non-critical issues
- `[INFO]` - Informational messages

### Test Markers

The testing framework uses industry-standard markers for test categorization:

- `unit` - Unit tests for individual components
- `integration` - Integration tests for component interactions
- `e2e` - End-to-end workflow tests
- `api` - API endpoint tests
- `database` - Database and model tests
- `frontend` - Frontend component tests
- `health` - System health verification
- `smoke` - Basic functionality verification
- `fast` - Quick execution tests
- `slow` - Longer-running tests

## System Architecture

### Backend Services

- **FastAPI Application**: RESTful API with automatic OpenAPI documentation
- **PDF Processing Engine**: Text extraction with character-level positioning
- **Citation Parser**: Intelligent citation detection and normalization
- **Database Layer**: SQLite with SQLAlchemy ORM for data persistence
- **Document Pipeline**: Orchestrated processing workflow

### Frontend Application

- **Next.js Framework**: React-based application with server-side rendering
- **Graph Visualization**: React Flow integration for interactive citation networks
- **Document Interface**: Comprehensive document browsing and analysis
- **Upload System**: Drag-and-drop PDF processing interface

### Data Storage

- **Document Storage**: Secure PDF file management
- **Citation Database**: Structured storage of extracted citations
- **Graph Data**: Citation relationship mapping and metadata

## API Reference

### Core Endpoints

- `GET /health` - System health status
- `GET /v1/documents` - Retrieve document list
- `GET /v1/documents/{id}` - Get document details and citations
- `GET /v1/documents/{id}/pdf` - Stream document PDF
- `GET /v1/graph` - Retrieve citation graph data
- `POST /v1/ingest` - Upload and process PDF documents
- `POST /v1/process` - Process all pending documents
- `POST /v1/process/{id}` - Process specific document

### API Documentation

Interactive API documentation is available at `/docs` when the backend is running.

## Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```bash
# Database Configuration
DATABASE_URL=sqlite:///./data/citations.db

# File Storage
PDF_STORAGE_PATH=./data/pdfs

# Service Ports
API_PORT=8000
FRONTEND_PORT=3000

# Feature Configuration
FEATURE_EXTERNAL_ENRICHMENT=false
MODEL_PROVIDER=openai

# Optional: OpenAI API Key
OPENAI_API_KEY=your_api_key_here
```

## Project Structure

```
├── backend/                 # Python FastAPI backend
│   ├── main.py             # Application entry point
│   ├── models.py           # Database models
│   ├── schemas.py          # Data validation schemas
│   ├── database.py         # Database configuration
│   ├── pdf_processor.py    # PDF text extraction
│   ├── citation_parser.py  # Citation parsing logic
│   └── document_processor.py # Document processing pipeline
├── frontend/               # Next.js frontend application
│   ├── src/app/           # Application pages
│   ├── src/components/    # React components
│   └── src/lib/           # Utilities and API client
├── tests/                  # Comprehensive test suite
│   ├── conftest.py        # Test configuration and fixtures
│   ├── test_health.py     # Health check tests
│   ├── test_api_endpoints.py # API endpoint tests
│   ├── test_models.py     # Database model tests
│   ├── test_citation_parser.py # Citation parser tests
│   ├── test_integration.py # Integration tests
│   └── test_frontend_components.py # Frontend tests
├── data/                   # Data storage directory
│   └── pdfs/              # PDF document storage
├── cursor/                 # Project documentation
├── docs/                   # Additional documentation
├── docker-compose.yml      # Production Docker configuration
├── docker-compose.dev.yml  # Development Docker configuration
├── Dockerfile              # Backend Docker image
├── frontend/Dockerfile     # Frontend Docker image
├── health_check.py         # System health verification
├── run_test_suite.py       # Comprehensive test runner
├── deploy.sh               # Linux/Mac deployment script
├── deploy.ps1              # Windows deployment script
└── requirements.txt        # Python dependencies
```

## Development Status

### Completed Components

✅ **Core Infrastructure**
- Project structure and dependency management
- Database schema and ORM models
- PDF text extraction pipeline
- Citation parsing system
- RESTful API implementation
- Frontend application framework
- Interactive graph visualization
- Docker containerization
- Production deployment scripts

✅ **Testing Framework**
- Comprehensive test suite with pytest
- Health check system
- Test categorization and markers
- Automated test execution
- JUnit XML and HTML reporting

### Active Development

🚧 **Current Focus**
- Enhanced citation extraction accuracy
- LLM integration for citation resolution
- Performance optimization

### Planned Features

📋 **Future Development**
- CourtListener API integration
- Advanced citation confidence scoring
- Batch processing analytics
- Neo4j graph database adapter

## Technical Approach

The system follows a deterministic-first philosophy:

1. **Document Processing**: Extract text with precise character positioning
2. **Citation Detection**: Apply rule-based citation parsing
3. **Normalization**: Standardize citations using proven libraries
4. **Relationship Mapping**: Build citation networks deterministically
5. **AI Enhancement**: Use machine learning for ambiguous case resolution
6. **Confidence Assessment**: Transparent scoring based on data quality

## Quality Assurance

### Testing Strategy

- **Unit Tests**: Individual component validation
- **Integration Tests**: Component interaction verification
- **End-to-End Tests**: Complete workflow validation
- **Health Checks**: System operational verification

### Code Quality

- **Type Safety**: Comprehensive type annotations
- **Documentation**: Inline code documentation
- **Standards**: PEP 8 compliance and best practices
- **Coverage**: Comprehensive test coverage

## Contributing

Detailed engineering documentation is available in the `/cursor` directory:
- `/cursor/eng/` - Technical specifications and architecture
- `/cursor/ai/` - AI integration guidelines and policies
- `/cursor/product/` - Product requirements and scope

## Support and Troubleshooting

### Common Issues

1. **Docker Container Issues**: Use `docker-compose logs` to view service logs
2. **Port Conflicts**: Verify ports 3000 and 8000 are available
3. **Database Issues**: Check database file permissions in the data directory

### Health Check Failures

If health checks fail:
1. Verify Docker containers are running: `docker ps`
2. Check service logs: `docker-compose logs [service-name]`
3. Verify network connectivity between services
4. Check file permissions and directory structure

## License

This project adheres to the constraints outlined in `/cursor/product/non_goals.md`. The system does not download copyrighted content, generate hallucinated links, or rely on unproven legal NLP approaches.
