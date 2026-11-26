#!/usr/bin/env bash
# Assistant J-ed pour Linux (2.0.3) : lance le menu texte, jumeau de la fenêtre de l'assistant Windows.
# Utilisation, depuis le Terminal :  bash ~/J-ed/<dossier de J-ed>/j-ed.sh
# Ne pas lancer avec sudo : les fichiers de J-ed appartiendraient à root (décision D4).
set -u
ICI="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
UID_ACTUEL="${JED_UID_ACTUEL:-$(id -u)}"   # JED_UID_ACTUEL : réservé aux tests automatiques
if [ "$UID_ACTUEL" = "0" ]; then
  echo "Ne lancez pas l'assistant en administrateur (sudo ou root) : relancez-le depuis votre compte, sans sudo." >&2
  exit 1
fi
if ! command -v pwsh >/dev/null 2>&1; then
  echo "PowerShell 7 n'est pas installé : l'assistant J-ed en a besoin sous Linux." >&2
  echo "Voir « Avant de commencer (Linux) », partie PowerShell (paquet .deb de la page des versions de PowerShell sur GitHub)." >&2
  exit 1
fi
exec pwsh -NoProfile -File "$ICI/assistant/menu-j-ed.ps1" "$@"
