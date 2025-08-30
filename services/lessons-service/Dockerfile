FROM python:3.11-slim

WORKDIR /app

COPY ./main.py /app/main.py

RUN pip install --no-cache-dir fastapi uvicorn pydantic

EXPOSE 8018

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
