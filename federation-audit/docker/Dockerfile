FROM python:3.11-bookworm@sha256:c17b9ca6def1a936e55c77f086aaaf5f6a6c5f4d2fb4b7ac8c0113ba94e8b6ab

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /audit
COPY pyproject.toml README.md ./
COPY src ./src
COPY contracts ./contracts
COPY manifests ./manifests
COPY runtime ./runtime
RUN python -m pip install --no-cache-dir .
USER pwuser
ENTRYPOINT ["federation-audit"]
