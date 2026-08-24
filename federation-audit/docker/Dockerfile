FROM mcr.microsoft.com/playwright:v1.62.1-noble@sha256:dcc5531e97840b9b5e794f2814476b21571c5124a3fca2267d73041f56e7580e

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /audit
COPY pyproject.toml README.md ./
COPY src ./src
COPY contracts ./contracts
COPY manifests ./manifests
COPY runtime ./runtime
COPY playwright ./playwright
RUN python -m pip install --no-cache-dir . && cd playwright && npm ci --no-audit --no-fund
USER pwuser
ENTRYPOINT ["federation-audit"]
