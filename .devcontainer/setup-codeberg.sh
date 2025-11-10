#!/bin/bash
set -e

echo "🔧 Setting up Codeberg repository..."

# Check if CODEBERG_TOKEN is set
if [ -z "$CODEBERG_TOKEN" ]; then
    echo "⚠️  CODEBERG_TOKEN environment variable is not set."
    echo "📝 Please set it in Gitpod user settings:"
    echo "   https://app.gitpod.io/settings/variables"
    echo ""
    echo "   Variable name: CODEBERG_TOKEN"
    echo "   Variable value: <your-personal-access-token>"
    echo "   Scope: */* (or codeberg.org/lpv/*)"
    echo ""
    echo "⏭️  Skipping automatic repository clone."
    exit 0
fi

# Configure Git to use the token for Codeberg
echo "🔐 Configuring Git credentials for Codeberg..."
git config --global credential.helper store

# Create credentials file with token
mkdir -p ~/.git-credentials-temp
echo "https://${CODEBERG_USERNAME}:${CODEBERG_TOKEN}@codeberg.org" > ~/.git-credentials

# Set proper permissions
chmod 600 ~/.git-credentials

# Configure Git user (you can customize these)
git config --global user.name "${CODEBERG_USERNAME}"
git config --global user.email "${CODEBERG_USERNAME}@users.codeberg.org"

# Clone the repository if it doesn't exist
REPO_NAME=$(basename "$CODEBERG_REPO_URL" .git)
CLONE_PATH="/workspaces/${REPO_NAME}"

if [ -d "$CLONE_PATH" ]; then
    echo "📁 Repository already exists at $CLONE_PATH"
    cd "$CLONE_PATH"
    echo "🔄 Pulling latest changes..."
    git pull || echo "⚠️  Could not pull changes (this is normal if there are local modifications)"
else
    echo "📥 Cloning repository to $CLONE_PATH..."
    git clone "$CODEBERG_REPO_URL" "$CLONE_PATH"
    cd "$CLONE_PATH"
    echo "✅ Repository cloned successfully!"
fi

echo ""
echo "✨ Setup complete!"
echo "📂 Repository location: $CLONE_PATH"
echo ""
