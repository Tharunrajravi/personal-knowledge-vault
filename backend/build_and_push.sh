#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# build_and_push.sh — Build Docker image and push to ECR
#
# Run this after local testing to push your image to AWS.
# ECS will pull this image when deploying.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

source /home/tharunraj/.env

IMAGE_TAG="${1:-latest}"  # pass a tag as arg, default = latest
FULL_IMAGE="$ECR_REPO_URI:$IMAGE_TAG"
LATEST_IMAGE="$ECR_REPO_URI:latest"

echo "╔══════════════════════════════════════════╗"
echo "║  PKV — Build + Push to ECR               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  ECR:   $ECR_REPO_URI"
echo "  Tag:   $IMAGE_TAG"
echo "  Region: $REGION"
echo ""

# ── 1. Authenticate Docker to ECR ─────────────────────────────────
echo "[1/4] Authenticating Docker with ECR..."
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin \
  "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
echo "  ✓ Authenticated"

# ── 2. Build image ─────────────────────────────────────────────────
echo ""
echo "[2/4] Building Docker image..."
cd "$(dirname "$0")"

docker build \
  --target final \
  --platform linux/amd64 \
  -t $FULL_IMAGE \
  -t $LATEST_IMAGE \
  .

echo "  ✓ Image built: $FULL_IMAGE"

# Show image size
SIZE=$(docker image inspect $FULL_IMAGE --format='{{.Size}}' | numfmt --to=iec-i --suffix=B 2>/dev/null || echo "unknown")
echo "  ✓ Image size: $SIZE"

# ── 3. Push to ECR ─────────────────────────────────────────────────
echo ""
echo "[3/4] Pushing to ECR..."
docker push $FULL_IMAGE
docker push $LATEST_IMAGE
echo "  ✓ Pushed: $FULL_IMAGE"

# ── 4. Verify in ECR ───────────────────────────────────────────────
echo ""
echo "[4/4] Verifying in ECR..."
aws ecr describe-images \
  --repository-name "$PROJECT-backend" \
  --region $REGION \
  --query 'sort_by(imageDetails, &imagePushedAt)[-3:].{Tag:imageTags[0],Size:imageSizeInBytes,Pushed:imagePushedAt}' \
  --output table

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Image pushed successfully!              ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Image URI: $FULL_IMAGE"
echo ""
echo "  Next: Day 3 — run infra/aws/06_ecs_alb.sh to deploy to ECS"
echo ""
