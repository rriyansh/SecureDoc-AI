# SecureDoc AI Deployment Guide

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+ (for production)
- Redis 7+ (for caching)
- Qdrant (vector database)

## Environment Variables

See `.env.example` for all configuration options.

## Local Development

```bash
# Setup
make install
make up

# Build index
make build-index

# Run API
make run-api

# Run tests
make test
```

## Docker Deployment

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

## Production Deployment

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n secure-doc-ai
```

### Database Migrations

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Monitoring

- Prometheus metrics: `/metrics`
- Health checks: `/health`, `/ready`
- Structured logs: JSON format

## Security

- Rotate secrets regularly: `scripts/rotate_keys.sh`
- Audit logs in `audit/`
- TLS termination at ingress