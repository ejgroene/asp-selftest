FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Install Python 3.12 (default version for Ubuntu 24.04) and development tools
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
