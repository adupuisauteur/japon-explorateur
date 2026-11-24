# Service Argos Translate de J-ed (version 2.0.0 ; profil Docker « hors-ligne » jusqu'au lot 7).
# Image séparée : l'application principale ne reçoit ni PyTorch ni Argos.
# Construite sur votre poste par « docker compose --profile hors-ligne up -d --build ».
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARGOS_PACKAGES_DIR=/argos/packages \
    XDG_DATA_HOME=/argos/data \
    XDG_CACHE_HOME=/argos/cache \
    ARGOS_DEPOT_DIR=/depot \
    HF_HUB_OFFLINE=1 \
    ARGOS_DEVICE_TYPE=cpu

WORKDIR /service
COPY requirements.txt .
# PyTorch « CPU » (sans CUDA) depuis l'index officiel de PyTorch ; le reste depuis PyPI. Versions figées.
# 2.0.2-rc5 (R7) : réseau lent ou proxy : délai de 120 s et 10 nouvelles tentatives (pip : 15 s et 5 par défaut).
RUN pip install --timeout 120 --retries 10 --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY server.py .
RUN useradd --create-home --uid 1000 argos \
 && mkdir -p /argos/packages /argos/data /argos/cache /depot \
 && chown -R argos:argos /argos /service

USER argos
# Port interne au réseau Docker du projet : il n'est PAS publié sur le poste.
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4)"
CMD ["python", "server.py"]
