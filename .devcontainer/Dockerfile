FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        aardvark-dns \
        dbus-user-session \
        fuse-overlayfs \
        just \
        libatk-bridge2.0-0t64 \
        libatk1.0-0t64 \
        libxcomposite1 \
        libxdamage1 \
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
