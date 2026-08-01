FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite DB lives here — mount a volume at this path in production
# so chat history survives redeploys.
VOLUME ["/app/data"]
ENV DB_PATH=/app/data/chat_history.db

EXPOSE 9999

CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "9999"]
