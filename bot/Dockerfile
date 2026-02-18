FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY clawdia/ clawdia/

RUN useradd --create-home clawdia
USER clawdia

CMD ["python", "-m", "clawdia"]
