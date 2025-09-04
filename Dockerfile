# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# 1) env first (applies to all later layers)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 2) base tools you want in dev (curl for healthchecks)
RUN apt-get update \
 && apt-get install -y curl \
 && rm -rf /var/lib/apt/lists/*

# 3) workdir
WORKDIR /app

# 4) install deps (cached separately from app code)
COPY app/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# 5) copy your app
COPY app /app/app

# 6) runtime env + port + default command
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host","0.0.0.0","--port","8000"]