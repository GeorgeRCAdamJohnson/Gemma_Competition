FROM python:3.13-slim

# Real harness deps: google-adk + friends from PyPI; our three harness packages come
# from harness_src/x on PYTHONPATH (adk_submission 0.2.13, adk_eval_core 0.1.0, swegemma 0.2.11).
# Toolchain mirrors comp_files/Dockerfile.public (the official public sandbox).
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends git patch protobuf-compiler pigz \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'google-adk[extensions]==1.36.1' google-genai==2.11.0 pyyaml python-dotenv \
    && pip install --no-cache-dir pytest pytest-timeout==2.1.0 typer pygments packaging \
    && pip install --no-cache-dir requests httpx docker

ENV PYTHONPATH=/x
WORKDIR /rig
