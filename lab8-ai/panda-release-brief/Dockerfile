FROM python:3.12.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY tests ./tests
COPY skills ./skills
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home app && mkdir /reports && chown app:app /reports
USER app
CMD ["uvicorn", "src.agent:app", "--host", "0.0.0.0", "--port", "8080"]
