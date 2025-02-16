FROM python:3.10

WORKDIR /app

COPY watcher.py .

RUN pip install pymongo

CMD ["python", "watcher.py"]
