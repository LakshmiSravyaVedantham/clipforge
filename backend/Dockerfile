FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg libsndfile1 git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# PIP_CONSTRAINT applies to isolated build envs too, so openai-whisper picks up old setuptools
RUN echo "setuptools<71.0.0" > /tmp/constraints.txt
ENV PIP_CONSTRAINT=/tmp/constraints.txt
RUN pip install --upgrade pip "setuptools<71.0.0" && pip install -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
