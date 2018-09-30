FROM python:3.7-slim-stretch

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

COPY app.py /

ENTRYPOINT ["python3", "/app.py"]