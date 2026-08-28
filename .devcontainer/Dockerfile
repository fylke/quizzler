FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends just openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Pre-create ~/.ssh so the Dev Containers known_hosts sync has a writable target
RUN mkdir -p /home/vscode/.ssh \
    && chown vscode:vscode /home/vscode/.ssh \
    && chmod 700 /home/vscode/.ssh

USER vscode

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/home/vscode/.local/bin:${PATH}"
