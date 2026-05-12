FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY memory_core ./memory_core
COPY run.py ./run.py

ENV MEMORY_CORE_DB_PATH=/data/memory_core.db
ENV MEMORY_CORE_HOST=0.0.0.0
ENV MEMORY_CORE_PORT=8765

VOLUME ["/data"]
EXPOSE 8765

CMD ["python", "run.py"]