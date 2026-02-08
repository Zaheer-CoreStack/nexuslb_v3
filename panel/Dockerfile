FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
# apache2-utils is needed for htpasswd command
RUN apt-get update && apt-get install -y \
    apache2-utils \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize DB (if needed, but app init handles it)
ENV FLASK_APP=app.py

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
