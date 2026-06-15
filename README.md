# Personal Knowledge Vault

A full-stack cloud-native bookmarking and knowledge management app built on AWS.

## Architecture

```
User → CloudFront → S3 (React SPA)
                 → ALB → ECS Fargate (FastAPI)
                              → RDS PostgreSQL
                              → ElastiCache Redis
                              → S3 (uploads/exports)
                              → SSM (secrets)
```

## Features

- Save URLs with auto-scraped metadata (title, description, favicon)
- YouTube and GitHub-specific metadata extraction
- Full-text search (PostgreSQL tsvector, GIN index)
- Tag links with custom colors
- Favorite links
- Dashboard analytics (charts, top domains, activity)
- Export to PDF → S3 presigned URL
- JWT auth with Redis refresh tokens
- Rate limiting

## AWS Services Used

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| ECS Fargate | Run FastAPI containers | 400 vCPU-hrs/mo |
| RDS PostgreSQL | Primary database | 750 hrs db.t3.micro |
| ElastiCache Redis | Cache + sessions | 750 hrs cache.t3.micro |
| S3 | Frontend + uploads | 5 GB |
| CloudFront | CDN + HTTPS | 1 TB transfer |
| ECR | Docker image registry | 500 MB |
| ALB | Load balancer + health checks | 750 hrs |
| SSM Parameter Store | Secrets management | Free |
| CloudWatch | Logs + metrics | 10 metrics free |

## Local Development

```bash
# Backend
cd backend
docker-compose up -d
# API at http://localhost:8000/docs

# Frontend
cd frontend
npm install
npm run dev
# App at http://localhost:3000
```

## Deploy

```bash
# Backend
cd backend
bash build_and_push.sh

# Frontend
cd frontend
bash deploy.sh

# Or just push to main — GitHub Actions handles everything
git push origin main
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

- `backend.yml` — triggers on changes to `backend/`
- `frontend.yml` — triggers on changes to `frontend/`
- `deploy-all.yml` — deploys both in parallel on every push to main

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | From `infra/aws/.github-secrets` |
| `AWS_SECRET_ACCESS_KEY` | From `infra/aws/.github-secrets` |
| `S3_BUCKET` | `pkv-frontend-919468641180` |
| `CF_DIST_ID` | `E2IUKC500WC3SF` |

## Project Structure

```
personal-knowledge-vault/
├── .github/workflows/
│   ├── backend.yml       # Backend CI/CD
│   ├── frontend.yml      # Frontend CI/CD
│   └── deploy-all.yml    # Deploy both in parallel
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI app
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── database.py   # Async PG + Redis
│   │   ├── config.py     # SSM-backed settings
│   │   └── routes/       # auth, links, scraper, tags, dashboard, export
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── build_and_push.sh
├── frontend/
│   ├── src/
│   │   ├── pages/        # Auth, Dashboard, Links, Tags
│   │   ├── components/   # Layout
│   │   ├── api/          # Axios client + services
│   │   └── store/        # Zustand auth store
│   ├── vite.config.js
│   └── deploy.sh
└── infra/
    └── aws/
        ├── 01_vpc.sh
        ├── 02_iam.sh
        ├── 03_rds.sh
        ├── 04_ecr_s3.sh
        ├── 05_verify.sh
        ├── 06_ecs_cluster.sh
        ├── 07_alb.sh
        ├── 08_ecs_service.sh
        ├── 09_elasticache.sh
        ├── 10_cloudfront.sh
        └── teardown.sh
```

## Live URL

https://d4jjnxuu7qbc7.cloudfront.net
# test
