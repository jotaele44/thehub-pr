FROM mcr.microsoft.com/playwright:v1.62.1-noble

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /audit
COPY pyproject.toml README.md ./
COPY src ./src
COPY contracts ./contracts
COPY manifests ./manifests
COPY runtime ./runtime
COPY playwright ./playwright
RUN python -m pip install --no-cache-dir . && cd playwright && npm install --no-audit --no-fund
USER pwuser
ENTRYPOINT ["federation-audit"]
