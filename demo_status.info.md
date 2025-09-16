# Text-to-Video Orchestrator

An open-source scaffold for an asynchronous text-to-video API service.

## ✨ Features
- **Async job lifecycle**: submit → queue → track → result
- **FastAPI gateway** for HTTP APIs
- **Redis Streams** as durable, high-speed event backbone
- **Rust worker** scaffold with at-least-once semantics and checkpointing
- **Kubernetes manifests** for API, worker, Redis, ingress
- **Minimal front-end** to submit and poll jobs

## 🚧 Status
This repo provides the **infrastructure backbone** for text-to-video generation.  
It does *not* include model weights or GPU-bound video generation yet.

**Progress so far**
- Async APIs, Redis-backed queue, worker scaffold
- Dockerized API + worker
- Kubernetes templates for multi-replica deployments
- Basic UI for job submission + status

**Next milestones**
- Integrate Genmo Mochi-1 model
- Artifact persistence to S3/MinIO
- Observability (Prometheus, Grafana, logging)
- Security (JWT/OIDC auth, rate limiting, RBAC)

## 🚀 Quickstart (local demo) - Will make a proper build setup runbook once I push some tests.
```bash
# 1. Start Redis
docker run --rm -p 6379:6379 redis:7

# 2. Run API
cd VideoGenerator_API/back-end
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 3. Run worker (placeholder)
cd ../rust-worker
cargo run