"""Diagnostic du service Argos (2.0.0) — à lancer DANS le conteneur argos :

    docker compose cp docker/argos/diagnostic.py argos:/tmp/diagnostic.py
    docker compose exec argos python /tmp/diagnostic.py

Affiche les versions, les paquets installés, la forme de leurs fichiers resources.json (clés seulement) et
le déroulé complet d'une traduction d'une phrase FICTIVE, étape par étape (ja→en puis en→fr), avec la pile
d'appels en cas d'erreur. N'utilise aucun texte de l'utilisateur, n'appelle pas Internet, ne modifie rien.
Le fichier est en ASCII (phrase japonaise écrite en \\u) pour éviter tout problème d'accents sous Windows.
"""
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, "/service")
SENTENCE = "これは試験用の短い文です。"  # phrase fictive


def section(title):
    print(f"\n=== {title}")


def main():
    import server

    section("Versions")
    for name in ("argostranslate", "stanza", "ctranslate2", "sentencepiece", "minisbd", "torch"):
        try:
            from importlib.metadata import version

            print(f"{name} {version(name)}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name} : introuvable ({exc.__class__.__name__})")

    import argostranslate.package as package

    section("Paquets installés")
    for pkg in package.get_installed_packages():
        print(f"{pkg.from_code}->{pkg.to_code} {pkg.package_version} ; découpage : {pkg.packaged_sbd_path}")
        resources = Path(str(pkg.package_path)) / "stanza" / "resources.json"
        if resources.is_file():
            data = json.loads(resources.read_text(encoding="utf-8"))
            for lang, entry in data.items():
                if isinstance(entry, dict):
                    print(f"    resources.json [{lang}] clés : {sorted(entry)[:20]}")
                    if "default_processors" in entry:
                        print(f"        default_processors : {entry['default_processors']}")
                    if "tokenize" in entry and isinstance(entry["tokenize"], dict):
                        print(f"        tokenize : {sorted(entry['tokenize'])}")
            adapted = server.compatible_stanza_resources(resources.parent, pkg.from_code,
                                                         cache_dir="/tmp/diagnostic-stanza")
            print(f"    copie adaptée par J-ed : {adapted or 'aucune (format déjà compatible ou non reconnu)'}")
        stanza_dir = Path(str(pkg.package_path)) / "stanza"
        if stanza_dir.is_dir():
            print(f"    contenu de stanza/ : {sorted(p.relative_to(stanza_dir).as_posix() for p in stanza_dir.rglob('*') if p.is_file())[:30]}")

    backend = server.ArgosBackend("/depot")
    for source, target in (("ja", "en"), ("en", "fr")):
        section(f"Traduction d'essai {source}->{target}")
        text = SENTENCE if source == "ja" else "This is a short test sentence."
        try:
            print("Résultat :", backend.translate_step([text], source, target))
        except Exception:  # noqa: BLE001 — la pile complète est le but de ce diagnostic
            traceback.print_exc(file=sys.stdout)


if __name__ == "__main__":
    main()
