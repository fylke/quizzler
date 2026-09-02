FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        aardvark-dns \
        dbus-user-session \
        fonts-liberation \
        fuse-overlayfs \
        just \
        libasound2t64 \
        libatk-bridge2.0-0t64 \
        libatk1.0-0t64 \
        libatspi2.0-0t64 \
        libcairo2 \
        libcups2t64 \
        libdbus-1-3 \
        libdrm2 \
        libegl1 \
        libgbm1 \
        libglib2.0-0t64 \
        libgtk-3-0t64 \
        libnspr4 \
        libnss3 \
        libpango-1.0-0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libxshmfence1 \
        netavark \
        nftables \
        openssh-client \
        podman \
        podman-compose \
        slirp4netns \
        uidmap \
    && rm -rf /var/lib/apt/lists/*

# Rootless Podman needs subordinate ID ranges for user namespaces.
RUN usermod --add-subuids 100000-165535 --add-subgids 100000-165535 vscode

# Pre-create ~/.ssh so the Dev Containers known_hosts sync has a writable target
RUN mkdir -p /home/vscode/.ssh \
    && chown vscode:vscode /home/vscode/.ssh \
    && chmod 700 /home/vscode/.ssh

USER vscode

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/home/vscode/.local/bin:${PATH}"
