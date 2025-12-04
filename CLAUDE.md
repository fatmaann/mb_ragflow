# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFlow is an open-source RAG (Retrieval-Augmented Generation) engine based on deep document understanding. It's a full-stack application with:
- Python backend (Flask-based API server)
- React/TypeScript frontend (built with UmiJS)
- Microservices architecture with Docker deployment
- Multiple data stores (MySQL, Elasticsearch/Infinity, Redis, MinIO)

## Architecture

### Backend (`/api/`)
- **Main Server**: `api/ragflow_server.py` - Flask application entry point
- **Apps**: Modular Flask blueprints in `api/apps/` for different functionalities (kb_app.py, dialog_app.py, document_app.py, canvas_app.py, file_app.py, etc.)
- **Services**: Business logic in `api/db/services/`
- **Models**: Database models in `api/db/db_models.py`

### Core Processing (`/rag/`)
- **Document Processing**: `deepdoc/` - PDF parsing, OCR, layout analysis
- **LLM Integration**: `rag/llm/` - Model abstractions (chat_model.py, embedding_model.py, rerank_model.py, cv_model.py, tts_model.py)
- **RAG Pipeline**: `rag/flow/` - Chunking, parsing, tokenization
- **Graph RAG**: `graphrag/` - Knowledge graph construction and querying

### Agent System (`/agent/`)
- **Components** (`agent/component/`): Modular workflow components (llm.py, categorize.py, iteration.py, switch.py, etc.)
- **Templates**: Pre-built agent workflows in `agent/templates/`
- **Tools** (`agent/tools/`): External API integrations (tavily.py, wikipedia.py, exesql.py, duckduckgo.py, arxiv.py, etc.)

### Frontend (`/web/`)
- React/TypeScript with UmiJS framework
- Ant Design + shadcn/ui components
- State management with Zustand
- Tailwind CSS for styling

### Python SDK (`/sdk/python/ragflow_sdk/`)
- Client library for RAGFlow API (ragflow.py)
- Modules: dataset.py, document.py, chunk.py, chat.py, session.py, agent.py

## Common Development Commands

### Backend Development
```bash
# Install Python dependencies
uv sync --python 3.10 --all-extras
uv run download_deps.py
pre-commit install

# Add to /etc/hosts for local development
# 127.0.0.1 es01 infinity mysql minio redis sandbox-executor-manager

# Start dependent services (MySQL, Elasticsearch, Redis, MinIO)
docker compose -f docker/docker-compose-base.yml up -d

# Run backend (requires services to be running)
source .venv/bin/activate
export PYTHONPATH=$(pwd)
bash docker/launch_backend_service.sh

# Linting
ruff check
ruff format
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run tests by priority level (p1=smoke, p2=core, p3=full)
uv run pytest --level=p1
uv run pytest --level=p2

# Run specific test file
uv run pytest test/testcases/test_web_api/test_kb_app/test_create_kb.py

# Run tests by client type
uv run pytest --client-type=http
uv run pytest --client-type=python_sdk
uv run pytest --client-type=web

# Tests require ZHIPU_AI_API_KEY environment variable
export ZHIPU_AI_API_KEY=your_key
```

### Frontend Development
```bash
cd web
npm install
npm run dev        # Development server
npm run build      # Production build
npm run lint       # ESLint
npm run test       # Jest tests
```

### Docker Development
```bash
# Full stack with Docker
cd docker
docker compose -f docker-compose.yml up -d

# Check server status
docker logs -f ragflow-server

# Rebuild images
docker build --platform linux/amd64 -f Dockerfile -t infiniflow/ragflow:nightly .

# Stop services and clean up
pkill -f "ragflow_server.py|task_executor.py"
```

## Key Configuration Files

- `docker/.env` - Environment variables for Docker deployment
- `docker/service_conf.yaml.template` - Backend service configuration
- `pyproject.toml` - Python dependencies and project configuration
- `web/package.json` - Frontend dependencies and scripts

## Testing Structure

- **Priority markers**: p1 (smoke), p2 (core), p3 (full) - tests include progressively more cases
- **Test suites**:
  - `test/testcases/test_web_api/` - Web API tests
  - `test/testcases/test_http_api/` - HTTP API tests
  - `test/testcases/test_sdk_api/` - Python SDK tests
  - `test/unit_test/` - Unit tests
  - `sdk/python/test/` - SDK-specific tests

## Database Engines

RAGFlow supports switching between Elasticsearch (default) and Infinity:
- Set `DOC_ENGINE=infinity` in `docker/.env` to use Infinity
- Requires container restart: `docker compose down -v && docker compose up -d`

## Development Environment Requirements

- Python 3.10-3.12
- Node.js >=18.20.4
- Docker & Docker Compose
- uv package manager
- jemalloc (`brew install jemalloc` on macOS)
- 16GB+ RAM, 50GB+ disk space