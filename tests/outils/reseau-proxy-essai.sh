#!/usr/bin/env bash
# J-ed 2.0.3 — « Essais Docker », scénario proxy : imite un réseau qui impose son proxy (comme celui de
# l'utilisateur). Outil de recette pour une machine jetable de GitHub, JAMAIS pour un ordinateur réel : il installe
# un proxy d'essai (tinyproxy), règle le service Docker comme le guide « Avant de commencer (Linux) » le demande
# (/etc/docker/daemon.json, clé « proxies »), puis coupe l'accès direct au web (ports 80 et 443) :
#   - pour le compte d'essai (premier argument) et pour root (service Docker) : seul le proxy sort ;
#   - pour les conteneurs (chaîne DOCKER-USER) : seul le proxy sort.
# Le compte « runner » de GitHub garde son accès, sinon la machine perdrait le contact avec GitHub.
# Écrit l'adresse du proxy dans le fichier donné en second argument.
set -euo pipefail

if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  echo "ARRÊT : cet outil coupe l'accès à Internet ; il ne tourne que sur une machine jetable de GitHub." >&2
  exit 2
fi
COMPTE="$1"
SORTIE="$2"
PORT=8888

sudo apt-get update -qq
# gsettings, schémas du proxy de GNOME et dconf : pour régler le proxy « dans les réglages d'Ubuntu ».
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tinyproxy jq dbus libglib2.0-bin \
  gsettings-desktop-schemas dconf-gsettings-backend dconf-service >/dev/null

# Adresse de la machine vue depuis les conteneurs (pas 127.0.0.1, qui serait le conteneur lui-même).
ADRESSE=$(ip -4 route get 1.1.1.1 | awk '{for (i = 1; i <= NF; i++) if ($i == "src") print $(i + 1)}')
PROXY="http://${ADRESSE}:${PORT}"

printf '%s\n' \
  'User tinyproxy' 'Group tinyproxy' "Port ${PORT}" 'Timeout 600' \
  'LogFile "/var/log/tinyproxy/tinyproxy.log"' 'LogLevel Info' 'MaxClients 200' \
  'Allow 127.0.0.1' 'Allow 10.0.0.0/8' 'Allow 172.16.0.0/12' 'Allow 192.168.0.0/16' \
  'ConnectPort 443' 'ConnectPort 80' \
  | sudo tee /etc/tinyproxy/tinyproxy.conf >/dev/null
sudo systemctl restart tinyproxy

# Service Docker : comme le guide (partie « Docker derrière le proxy »).
FICHIER=/etc/docker/daemon.json
[ -s "$FICHIER" ] || echo '{}' | sudo tee "$FICHIER" >/dev/null
sudo jq --arg p "$PROXY" '.proxies = {"http-proxy": $p, "https-proxy": $p, "no-proxy": "localhost,127.0.0.1"}' "$FICHIER" \
  | sudo tee "$FICHIER.nouveau" >/dev/null
sudo mv "$FICHIER.nouveau" "$FICHIER"
sudo systemctl restart docker
for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done

# Accès direct coupé (IPv4 et IPv6). L'ordre compte : règles insérées en tête.
UID_ESSAI=$(id -u "$COMPTE")
for outil in iptables ip6tables; do
  for uid in "$UID_ESSAI" 0; do
    sudo "$outil" -I OUTPUT 1 -p tcp -m multiport --dports 80,443 -m owner --uid-owner "$uid" -j REJECT
  done
  sudo "$outil" -N DOCKER-USER 2>/dev/null || true
  sudo "$outil" -I DOCKER-USER 1 -p tcp -m multiport --dports 80,443 -j REJECT
done

echo "Proxy d'essai : ${PROXY} (accès direct au web coupé pour ${COMPTE}, root et les conteneurs)"
echo "$PROXY" > "$SORTIE"
