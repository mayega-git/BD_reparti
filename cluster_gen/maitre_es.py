"""Module 4 — Interrogation du maître Elasticsearch."""

import json
import socket
import urllib.error
import urllib.request


def interroger_maitre(ip_maitre):
    url = f"http://{ip_maitre}:9201/_cat/nodes?format=json&h=name,ip"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"noeuds": data}
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError, OSError):
        return None
