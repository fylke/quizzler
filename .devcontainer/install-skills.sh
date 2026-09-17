#!/bin/sh

set -eu

export DISABLE_TELEMETRY=1

npx --yes skills add anthropics/skills \
  --skill webapp-testing \
  --agent github-copilot \
  --yes
npx --yes skills add trailofbits/skills \
  --skill property-based-testing \
  --agent github-copilot \
  --yes
npx --yes skills add openai/skills \
  --skill security-best-practices \
  --agent github-copilot \
  --yes
npx --yes skills add openai/skills \
  --skill security-threat-model \
  --agent github-copilot \
  --yes
npx --yes skills add obra/superpowers \
  --skill systematic-debugging \
  --agent github-copilot \
  --yes
npx --yes skills add obra/superpowers \
  --skill verification-before-completion \
  --agent github-copilot \
  --yes