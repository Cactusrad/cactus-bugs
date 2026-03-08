#!/bin/bash
# Auto-deploy script for bugs_service based on git tags.
#
# Cron to add on the server:
# */2 * * * * /root/bugs_service/scripts/auto-deploy-tag.sh >> /var/log/bugs_auto_deploy.log 2>&1

set -e

DEPLOY_DIR="${DEPLOY_DIR:-/root/bugs_service}"
TAG_FILE="/root/.current_deployed_tag_bugs"
LOG_PREFIX="[bugs-deploy $(date '+%Y-%m-%d %H:%M:%S')]"

cd "$DEPLOY_DIR"

# Fetch latest tags from remote
git fetch --tags --quiet

# Get latest tag on origin/master
LATEST_TAG=$(git describe --tags --abbrev=0 origin/master 2>/dev/null || echo "none")
CURRENT_TAG=$(cat "$TAG_FILE" 2>/dev/null || echo "none")

if [ "$LATEST_TAG" = "none" ]; then
    echo "$LOG_PREFIX No tags found on origin/master, skipping."
    exit 0
fi

if [ "$LATEST_TAG" = "$CURRENT_TAG" ]; then
    exit 0
fi

echo "$LOG_PREFIX New tag detected: $LATEST_TAG (current: $CURRENT_TAG)"
echo "$LOG_PREFIX Deploying..."

# Checkout the new tag
git checkout "$LATEST_TAG" --quiet

# Rebuild and restart containers
docker compose up -d --build

# Record deployed tag
echo "$LATEST_TAG" > "$TAG_FILE"

echo "$LOG_PREFIX Deploy complete: $LATEST_TAG"
