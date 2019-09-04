FROM python:3.6-slim

RUN apt update && apt install -y gcc make

COPY ./union_server /opt/

RUN pip install --no-cache-dir -I pika==1.1.0 PyYAML==5.1

WORKDIR /opt/rpc_server
