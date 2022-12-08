FROM python:3.11-alpine
WORKDIR /app
ADD . /app
ENTRYPOINT ["python", "-m", "metrics_analyzer"]
