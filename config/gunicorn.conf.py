"""Serveur web (2.0.0, lot 3) : nombre de processus selon le profil de machine (config/profil_machine.py).

WEB_CONCURRENCY, s'il est défini, garde la priorité (réglage standard de gunicorn).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.profil_machine import current  # noqa: E402

bind = "0.0.0.0:8000"
timeout = 180
accesslog = "-"
workers = int(os.environ.get("WEB_CONCURRENCY") or current()["web"])
