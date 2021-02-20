FROM python:3-slim

RUN apt-get update && apt-get -y --no-install-recommends install systemd && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

COPY app.py /

ENTRYPOINT ["python3", "/app.py"]