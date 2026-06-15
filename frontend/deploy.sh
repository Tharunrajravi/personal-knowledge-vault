#!/bin/bash
# =============================================================================
# deploy.sh — Build frontend and deploy to S3 + CloudFront
#
# What this does:
#   1. npm run build  → creates optimized dist/ folder
#   2. aws s3 sync    → uploads changed files only (fast re-deploys)
#   3. CloudFront invalidation → clears CDN cache so users get new version
#
# Run this every time you change the frontend.
# =============================================================================
set -euo pipefail

source /home/tharunraj/.env

echo "╔══════════════════════════════════════════╗"
echo "║   PKV Frontend Deploy                    ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  S3:          s3://$FRONTEND_BUCKET"
echo "  CloudFront:  $CF_ID"
echo "  CDN URL:     https://$CF_DOMAIN"
echo ""

# ── 1. Install dependencies ───────────────────────────────────────────────────
echo "[1/4] Installing dependencies..."
npm install --silent
echo "  ✓ Dependencies installed"

# ── 2. Build ──────────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Building React app..."

# Inject the CloudFront URL as the API base (empty = relative URLs, which is correct
# when served from CloudFront since /api/* goes to ALB via CF behavior)
VITE_API_URL="" npm run build

echo "  ✓ Build complete"
echo "  ✓ Output: dist/"
ls -lh dist/ | tail -5

# ── 3. Upload to S3 ───────────────────────────────────────────────────────────
echo ""
echo "[3/4] Uploading to S3..."

# HTML files: no cache (always fetch latest)
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
  --region $REGION \
  --exclude "*" \
  --include "*.html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --delete

# JS/CSS assets: cache forever (Vite adds content hash to filenames)
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
  --region $REGION \
  --exclude "*.html" \
  --cache-control "public, max-age=31536000, immutable" \
  --delete

echo "  ✓ Uploaded to s3://$FRONTEND_BUCKET"

# ── 4. Invalidate CloudFront cache ────────────────────────────────────────────
echo ""
echo "[4/4] Invalidating CloudFront cache..."

INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id $CF_ID \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)

echo "  ✓ Invalidation: $INVALIDATION_ID"
echo "  ⏳ Cache clears in ~30 seconds"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Deploy Complete!                       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Live URL: https://$CF_DOMAIN"
echo ""
echo "  First visit may take 30s for CloudFront to warm up."
echo "  API health: https://$CF_DOMAIN/api/health"
echo ""
