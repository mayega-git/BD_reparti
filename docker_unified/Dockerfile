FROM docker.elastic.co/elasticsearch/elasticsearch:8.13.0

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 iproute2 curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.py /usr/local/bin/vpdf-entrypoint.py
RUN chmod +x /usr/local/bin/vpdf-entrypoint.py

USER elasticsearch
ENTRYPOINT ["python3", "/usr/local/bin/vpdf-entrypoint.py"]
