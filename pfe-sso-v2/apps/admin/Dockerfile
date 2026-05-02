# Stage 1 : Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
# vite.config.js sets outDir: '../static/dist' → outputs to /app/static/dist
RUN npm run build

# Stage 2 : Flask API backend
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
# Copy the built React app (output at /app/static/dist in build stage)
COPY --from=frontend-build /app/static/dist ./static/dist
CMD ["python", "-u", "app.py"]
