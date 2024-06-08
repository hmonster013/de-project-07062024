FROM bitnami/spark:latest

COPY requirements.txt /opt/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /opt/requirements.txt