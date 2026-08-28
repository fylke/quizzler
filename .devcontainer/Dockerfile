FROM mcr.microsoft.com/devcontainers/python:1-3.14-trixie

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends just \
    && rm -rf /var/lib/apt/lists/*

USER vscode

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/home/vscode/.local/bin:${PATH}"
