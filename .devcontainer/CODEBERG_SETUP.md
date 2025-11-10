# Codeberg Repository Auto-Clone Setup

This devcontainer is configured to automatically clone your Codeberg repository on startup.

## Setup Instructions

### 1. Create a Personal Access Token in Codeberg

1. Go to [Codeberg Settings](https://codeberg.org/user/settings)
2. Navigate to **Applications** → **Manage Access Tokens**
3. Click **Generate New Token**
4. Configure the token:
   - **Token Name**: `Gitpod Environment` (or any descriptive name)
   - **Permissions**: Select `repo` (Full control of repositories)
5. Click **Generate Token**
6. **Copy the token immediately** (you won't see it again!)

### 2. Add Token to Environment

**Option A: Use Gitpod Secrets (if available in your plan)**
- Add the token to your Gitpod secrets
- Reference it in your environment configuration

**Option B: Set manually in each environment**
```bash
export CODEBERG_TOKEN="your-token-here"
```

**Option C: Store in devcontainer configuration (less secure)**
- Add to `.devcontainer/devcontainer.json` remoteEnv (not recommended for public repos)

### 3. Restart Your Environment

After adding the token:
- Stop this environment
- Start a new environment
- The repository will be automatically cloned to `/workspaces/asp-selftest`

## Manual Testing

To test the setup in the current environment without restarting:

```bash
# Set the token temporarily (replace with your actual token)
export CODEBERG_TOKEN="your-token-here"

# Run the setup script
bash .devcontainer/setup-codeberg.sh
```

## Repository Details

- **Username**: lpv
- **Repository**: https://codeberg.org/lpv/asp-selftest.git
- **Clone Location**: `/workspaces/asp-selftest`

## Troubleshooting

### Token not found
If you see "CODEBERG_TOKEN environment variable is not set":
- Verify the variable is added in Gitpod settings
- Check the scope matches your repository
- Restart the environment

### Authentication failed
If cloning fails with authentication errors:
- Verify your token has `repo` permissions
- Check the token hasn't expired
- Regenerate the token if needed

### Repository already exists
If the repository already exists, the script will:
- Skip cloning
- Attempt to pull latest changes
- Continue without errors

## Security Notes

- Never commit your Personal Access Token to the repository
- The token is stored in `~/.git-credentials` (not committed)
- Use Gitpod environment variables for secure token storage
- Tokens are scoped per environment and not shared
