"""
Service Argos Translate de J-ed (version 2.0.0 ; service créé en 1.3.0, décision A1).

Serveur HTTP interne (bibliothèque standard de Python), joignable seulement sur le réseau Docker du
projet : AUCUN port n'est publié. Il n'est démarré qu'avec le profil Docker « hors-ligne ».

Points d'accès (JSON) :
  GET  /health        → {"argos_version", "packages": [{"from", "to", "version", "name"}], "busy"}
  POST /translate     {"texts": […], "source": "ja", "target": "fr"} → {"translations": […], "path": [...]}
  POST /index         consulte l'index des paquets Argos (INTERNET) → {"packages": [{"from", "to", "version",
                      "name", "size"}]} ; seulement sur action de l'utilisateur dans l'application
  POST /install       {"from": "ja", "to": "en"} : télécharge depuis l'index (INTERNET) et installe
  POST /install-file  {"filename": "…argosmodel"} : installe un fichier déposé dans le dossier de dépôt
  POST /remove        {"from": "ja", "to": "en"} : désinstalle un paquet
  POST /install-sbd   {"from": "ja", "to": "en"} : télécharge (INTERNET) le modèle de découpage en phrases
                      d'un paquet installé depuis un fichier qui n'en contient pas

Règles :
- aucun téléchargement en dehors de /index et /install, que l'application n'appelle que sur action
  explicite et confirmée de l'utilisateur ; la traduction elle-même n'utilise jamais Internet ;
- le journal du serveur ne contient jamais de texte (ni original, ni traduction) : méthode, chemin,
  code de réponse et durée seulement ;
- une seule installation à la fois (réponse 409 sinon) ;
- langues limitées à celles du module (japonais, anglais, français).

Fonctionnement hors ligne (vérifié dans le code source d'argostranslate 1.11.0, stanza 1.10.1 et
minisbd 0.9.5, le 14 novembre 2026) : le découpage en phrases d'Argos peut, à la première traduction,
télécharger un fichier (resources.json de Stanza, ou modèle MiniSBD quand le paquet n'en contient pas).
Le service l'empêche : Stanza est appelé sans téléchargement (download_method=None) et une traduction
est refusée, avec un message clair, si le modèle MiniSBD nécessaire manque. Ce modèle (quelques Mo) est
récupéré pendant le téléchargement d'un paquet depuis l'index, ou sur demande explicite (/install-sbd).

Correctif 1.3.0-rc3 (constaté au protocole TR8, 14 novembre 2026) : les paquets de l'index (ja→en 1.1,
en→fr 1.9) livrent un resources.json de Stanza à l'ancien format, sans rubrique « packages ». Stanza 1.10
ne sait plus le lire (KeyError: 'packages') ; en ligne, il le remplaçait silencieusement par un fichier
téléchargé. Le service en lit une COPIE adaptée (rubrique « packages » reconstituée à partir de
« default_processors », découpage seul), écrite dans son cache : le paquet n'est pas modifié et rien
n'est téléchargé.
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LANGS = {"ja", "en", "fr"}
PIVOT = "en"
MAX_BODY = 4 * 1024 * 1024
RESERVED_PROJECTS = {"japon-explorateur", "japon-explorateur-essai"}
FILENAME = re.compile(r"^[A-Za-z0-9._-]{1,200}\.argosmodel$")


class ServiceError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# --------------------------------------------------------------------------- erreurs internes

_SAFE_KEY = re.compile(r"^[A-Za-z_][\w.\-]{0,40}$")


def error_label(exc):
    """Type de l'erreur, plus la clé d'une KeyError si c'est un identifiant court (jamais un texte).

    2.0.0 : « KeyError » seul ne permettait pas de savoir quelle donnée manquait (constat du 15 novembre 2026).
    """
    label = exc.__class__.__name__
    if isinstance(exc, KeyError) and len(exc.args) == 1 and isinstance(exc.args[0], str) \
            and _SAFE_KEY.match(exc.args[0]):
        label += f" : '{exc.args[0]}'"
    return label


def error_location(exc, depth=4):
    """Les derniers appels (fichier:ligne fonction), sans aucune valeur : de quoi trouver la cause."""
    frames = traceback.extract_tb(exc.__traceback__)[-depth:]
    return " < ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in reversed(frames))


# --------------------------------------------------------------------------- découpage en phrases (2.0.0)

#: « jed » (par défaut) : découpage par la ponctuation, fait par ce service ; « paquet » : modèle du paquet
#: (Stanza ou MiniSBD), comme en 1.3.0.
#: Constat du 15 novembre 2026 sur le poste de l'utilisateur : les modèles Stanza livrés dans les paquets
#: ja→en 1.1 et en→fr 1.9 (ja/tokenize/gsd.pt, en/tokenize/ewt.pt) datent d'une ancienne version de Stanza ;
#: Stanza 1.10.1 ne sait plus les charger (KeyError: 'feat_dropout'), toute traduction échouait. Or J-ed envoie
#: déjà des segments d'une phrase : un découpage par la ponctuation suffit, sans modèle ni téléchargement.
SENTENCE_SPLIT_MODE = os.environ.get("ARGOS_DECOUPAGE", "jed").strip().lower() or "jed"
_JA_END = "。！？!?"
_CLOSERS = "」』）)]】〉》\"'”’"
_OPENERS = "「『（(【〈《“"
#: abréviations anglaises courantes (texte intermédiaire ja→en→fr) : pas de fin de phrase après elles
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr", "no", "nos", "vol", "vols", "p", "pp", "ed",
                  "eds", "ch", "fig", "cf", "etc", "vs", "ca", "e.g", "i.e", "approx", "dept", "univ"}


def _ends_with_abbreviation(piece):
    word = re.split(r"[\s(]", piece.rstrip().rstrip("."))[-1].lower()
    return word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha())


def split_sentences(text):
    """Découpe un texte en phrases par la ponctuation ; ne perd aucun caractère utile.

    - japonais : fin après 。！？ hors citation (「…。」と言った。 reste une seule phrase) ;
    - langues à espaces : fin après . ! ? suivis d'un espace, sauf après une abréviation ou une initiale.
    """
    pieces, start, depth, i, n = [], 0, 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _OPENERS:
            depth += 1
        elif ch in "」』）)】〉》" and depth:
            depth -= 1
        elif ch in _JA_END or ch == ".":
            j = i + 1
            while j < n and text[j] in _JA_END + ".":
                j += 1  # « ！？ », « ... »
            closing = j
            while closing < n and text[closing] in _CLOSERS:
                closing += 1
            followed_by_space = closing >= n or text[closing].isspace()
            if ch == "." or (ch in "!?" and text[i - 1:i].isascii()):
                boundary = followed_by_space and not (ch == "." and _ends_with_abbreviation(text[start:i + 1]))
            else:  # ponctuation japonaise : fin de phrase hors citation, ou si la citation se ferme en fin de texte
                boundary = depth == 0 or followed_by_space
            if boundary:
                depth = 0
                pieces.append(text[start:closing])
                start = i = closing
                continue
            i = j
            continue
        i += 1
    pieces.append(text[start:])
    sentences = [piece.strip() for piece in pieces if piece.strip()]
    return sentences or [text]


def install_sentence_splitter(sbd_module, mode=None):
    """Remplace le découpage des paquets par split_sentences (mode « jed »). Retourne True si remplacé."""
    if (mode or SENTENCE_SPLIT_MODE) != "jed":
        return False

    def jed_split(self, text):
        return split_sentences(text)

    for name in ("StanzaSentencizer", "MiniSBDSentencizer", "SpacySentencizerSmall"):
        cls = getattr(sbd_module, name, None)
        if cls is not None:
            cls.split_sentences = jed_split
    return True


# --------------------------------------------------------------------------- Stanza hors ligne


def stanza_cache_dir():
    return Path(os.environ.get("XDG_CACHE_HOME") or "/tmp") / "japon-stanza"


def compatible_stanza_resources(model_dir, lang, cache_dir=None):
    """Chemin d'une copie de <model_dir>/resources.json lisible par Stanza 1.10, ou None si inutile.

    Ancien format (paquets Argos) : la langue n'a pas de rubrique « packages ». On la reconstitue avec le
    seul modèle de découpage (« tokenize ») déclaré par défaut, qui est celui fourni dans le paquet.
    Le fichier du paquet n'est jamais modifié ; la copie est écrite dans le cache du service.
    """
    source = Path(model_dir) / "resources.json"
    if not source.is_file():
        return None
    raw = source.read_bytes()
    resources = json.loads(raw.decode("utf-8"))
    key, seen = str(lang).strip().lower(), set()
    while isinstance(resources.get(key), dict) and "alias" in resources[key] and key not in seen:
        seen.add(key)
        key = resources[key]["alias"]
    entry = resources.get(key)
    if not isinstance(entry, dict) or "packages" in entry:
        return None
    tokenize = (entry.get("default_processors") or {}).get("tokenize") or next(iter(entry.get("tokenize") or {}), None)
    if not tokenize:
        return None
    entry["packages"] = {"default": {"tokenize": tokenize}}
    target_dir = Path(cache_dir) if cache_dir else stanza_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(source.resolve()).encode("utf-8") + b"\0" + raw).hexdigest()[:24]
    target = target_dir / f"resources-{key}-{digest}.json"
    if not target.is_file():
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(resources, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
    return str(target)


# --------------------------------------------------------------------------- moteur Argos réel


class ArgosBackend:
    """Accès à argostranslate. Importé à la demande : le serveur démarre même si la bibliothèque manque."""

    def __init__(self, depot_dir):
        self.depot_dir = Path(depot_dir)
        self._patched = False

    def _lib(self):
        try:
            import argostranslate.package as package
            import argostranslate.translate as translate
        except ImportError as exc:  # pragma: no cover - dépend de l'image
            raise ServiceError(500, "argos_absent", f"Bibliothèque Argos Translate non installée ({exc}).") from None
        if not self._patched:
            self._offline_stanza()
            import argostranslate.sbd as sbd

            install_sentence_splitter(sbd)  # 2.0.0 : découpage par J-ed (voir SENTENCE_SPLIT_MODE)
            self._patched = True
        return package, translate

    @staticmethod
    def _offline_stanza():
        """Stanza vérifie par défaut sur Internet son fichier resources.json : désactivé (paquet autonome)."""
        try:
            import stanza
        except ImportError:  # pragma: no cover
            return
        original = getattr(stanza.Pipeline, "_japon_original", stanza.Pipeline)

        def offline_pipeline(*args, **kwargs):
            kwargs.setdefault("download_method", None)
            lang = kwargs.get("lang", args[0] if args else None)
            if lang and kwargs.get("dir") and "resources_filepath" not in kwargs:
                adapted = compatible_stanza_resources(kwargs["dir"], lang)
                if adapted:
                    kwargs["resources_filepath"] = adapted
            return original(*args, **kwargs)

        offline_pipeline._japon_original = original
        stanza.Pipeline = offline_pipeline

    @staticmethod
    def _sbd_model(pkg):
        """Nom du modèle MiniSBD qu'il faudrait télécharger pour ce paquet, ou '' s'il n'en faut pas."""
        if SENTENCE_SPLIT_MODE == "jed":
            return ""  # 2.0.0 : découpage fait par J-ed, aucun modèle de découpage n'est nécessaire
        if getattr(pkg, "packaged_sbd_path", None) is not None:
            return ""  # modèle de découpage inclus dans le paquet (Stanza ou MiniSBD)
        try:
            from argostranslate.sbd import MiniSBDSentencizer
            from minisbd import models as minisbd_models
        except ImportError:  # pragma: no cover
            return ""
        lang = MiniSBDSentencizer.LANGUAGE_CODE_MAPPING.get(pkg.from_code, pkg.from_code)
        if lang not in minisbd_models.list_models():
            lang = "en"  # repli d'Argos (le japonais n'a pas de modèle MiniSBD)
        path = Path(minisbd_models.cache_dir) / minisbd_models.MODELS[lang]
        return "" if path.is_file() else lang

    def _prepare_sbd(self, pkg):
        """Télécharge le modèle MiniSBD manquant (appelé seulement sur action de l'utilisateur)."""
        lang = self._sbd_model(pkg)
        if not lang:
            return ""
        from minisbd import models as minisbd_models

        try:
            minisbd_models.get_model_file(lang)
        except Exception as exc:
            raise ServiceError(502, "telechargement_echoue",
                               f"Modèle de découpage en phrases non téléchargé ({exc.__class__.__name__}).") from None
        return lang

    def version(self):
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("argostranslate")
        except PackageNotFoundError:
            return "absente"

    @staticmethod
    def _describe(pkg, size=None):
        out = {"from": pkg.from_code, "to": pkg.to_code, "version": str(getattr(pkg, "package_version", "") or ""),
               "name": f"{getattr(pkg, 'from_name', pkg.from_code)} → {getattr(pkg, 'to_name', pkg.to_code)}"}
        if size is not None:
            out["size"] = size
        return out

    def _installed_packages(self, package):
        return [p for p in package.get_installed_packages() if getattr(p, "type", "translate") == "translate"]

    def installed(self):
        package, _ = self._lib()
        out = []
        for p in self._installed_packages(package):
            item = self._describe(p)
            item["sbd_ready"] = not self._sbd_model(p)
            out.append(item)
        return out

    def available(self):
        package, _ = self._lib()
        try:
            package.update_package_index()
            items = package.get_available_packages()
        except Exception as exc:  # réseau coupé, index illisible
            raise ServiceError(502, "index_injoignable", f"Index des paquets Argos injoignable ({exc.__class__.__name__}).") from None
        return [self._describe(p, getattr(p, "size", None)) for p in items
                if getattr(p, "type", "translate") == "translate" and p.from_code in LANGS and p.to_code in LANGS]

    def install_from_index(self, source, target):
        package, _ = self._lib()
        try:
            package.update_package_index()
            candidates = [p for p in package.get_available_packages() if (p.from_code, p.to_code) == (source, target)]
        except Exception as exc:
            raise ServiceError(502, "index_injoignable", f"Index des paquets Argos injoignable ({exc.__class__.__name__}).") from None
        if not candidates:
            raise ServiceError(404, "paquet_absent", f"Aucun paquet {source}→{target} dans l'index Argos.")
        chosen = max(candidates, key=lambda p: _version_key(getattr(p, "package_version", "")))
        try:
            path = Path(chosen.download())
        except Exception as exc:
            raise ServiceError(502, "telechargement_echoue", f"Téléchargement interrompu ({exc.__class__.__name__}).") from None
        self._install_path(package, path)
        try:  # fichier de téléchargement temporaire (comme AvailablePackage.install d'Argos)
            path.unlink()
        except OSError:
            pass
        result = self._describe(chosen)
        installed = [p for p in self._installed_packages(package) if (p.from_code, p.to_code) == (source, target)]
        result["sbd_model"] = self._prepare_sbd(installed[0]) if installed else ""
        return result

    def install_from_file(self, filename):
        package, _ = self._lib()
        if not FILENAME.match(filename or ""):
            raise ServiceError(400, "fichier_refuse", "Nom de fichier refusé (paquet .argosmodel attendu).")
        path = (self.depot_dir / filename).resolve()
        if path.parent != self.depot_dir.resolve() or not path.is_file():
            raise ServiceError(404, "fichier_absent", "Fichier introuvable dans le dossier de dépôt.")
        self._install_path(package, path)
        return {"installed": filename}

    @staticmethod
    def _install_path(package, path):
        try:
            package.install_from_path(str(path))
        except Exception as exc:
            raise ServiceError(422, "paquet_corrompu", f"Paquet illisible ou corrompu ({exc.__class__.__name__}).") from None

    def install_sbd(self, source, target):
        package, _ = self._lib()
        found = [p for p in self._installed_packages(package) if (p.from_code, p.to_code) == (source, target)]
        if not found:
            raise ServiceError(404, "paquet_absent", f"Paquet {source}→{target} non installé.")
        return {"sbd_model": self._prepare_sbd(found[0])}

    def remove(self, source, target):
        package, _ = self._lib()
        found = [p for p in self._installed_packages(package) if (p.from_code, p.to_code) == (source, target)]
        if not found:
            raise ServiceError(404, "paquet_absent", f"Paquet {source}→{target} non installé.")
        for p in found:
            package.uninstall(p)
        return {"removed": f"{source}→{target}"}

    def translate_step(self, texts, source, target):
        package, translate = self._lib()
        for p in self._installed_packages(package):
            if (p.from_code, p.to_code) == (source, target) and self._sbd_model(p):
                raise ServiceError(409, "sbd_absent", f"Modèle de découpage en phrases absent pour le paquet {source}→{target} : "
                                   "téléchargez-le dans Traduction → Moteurs locaux (la traduction n'utilise jamais Internet).")
        return [translate.translate(t, source, target) for t in texts]


def _version_key(value):
    try:
        from packaging.version import Version

        return (1, Version(str(value)))
    except Exception:  # noqa: BLE001 — version non normalisée : rangée avant les versions normalisées
        return (0, str(value))


# --------------------------------------------------------------------------- service


class Service:
    def __init__(self, backend):
        self.backend = backend
        self.install_lock = threading.Lock()

    def health(self):
        return {"argos_version": self.backend.version(), "packages": self.backend.installed(),
                "busy": self.install_lock.locked(), "sentence_split": SENTENCE_SPLIT_MODE}

    def path(self, source, target):
        have = {(p["from"], p["to"]) for p in self.backend.installed()}
        if (source, target) in have:
            return [source, target]
        if (source, PIVOT) in have and (PIVOT, target) in have:
            return [source, PIVOT, target]
        raise ServiceError(404, "paquet_absent", f"Paquets nécessaires à {source}→{target} non installés.")

    def translate(self, body):
        texts, source, target = body.get("texts"), body.get("source"), body.get("target")
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise ServiceError(400, "requete", "« texts » doit être une liste de textes.")
        _check_pair(source, target)
        path = self.path(source, target)
        out = texts
        for a, b in zip(path, path[1:]):
            out = self.backend.translate_step(out, a, b)
        return {"translations": out, "path": path}

    def _exclusive(self, func, *args):
        if not self.install_lock.acquire(blocking=False):
            raise ServiceError(409, "occupe", "Une installation de paquet est déjà en cours.")
        try:
            return func(*args)
        finally:
            self.install_lock.release()

    def install(self, body):
        source, target = body.get("from"), body.get("to")
        _check_pair(source, target)
        return self._exclusive(self.backend.install_from_index, source, target)

    def install_file(self, body):
        return self._exclusive(self.backend.install_from_file, body.get("filename"))

    def remove(self, body):
        source, target = body.get("from"), body.get("to")
        _check_pair(source, target)
        return self._exclusive(self.backend.remove, source, target)

    def install_sbd(self, body):
        source, target = body.get("from"), body.get("to")
        _check_pair(source, target)
        return self._exclusive(self.backend.install_sbd, source, target)


def _check_pair(source, target):
    if source not in LANGS or target not in LANGS or source == target:
        raise ServiceError(400, "langue_non_prise", "Paire de langues non prise en charge.")


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "jed-argos/2.0.0"

        def log_message(self, fmt, *args):  # aucun texte : méthode, chemin, code
            return

        def _send(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _log(self, status, started, error=""):
            detail = f" — {error}" if error else ""
            sys.stderr.write(f"{self.command} {self.path} {status} {int((time.monotonic() - started) * 1000)} ms{detail}\n")

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ServiceError(413, "trop_long", "Requête trop volumineuse.")
            if not length:
                return {}
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ServiceError(400, "requete", "Corps JSON invalide.") from None
            if not isinstance(data, dict):
                raise ServiceError(400, "requete", "Objet JSON attendu.")
            return data

        def _dispatch(self, routes):
            started = time.monotonic()
            status, error = 200, ""
            try:
                route = routes.get(self.path.split("?")[0])
                if route is None:
                    raise ServiceError(404, "inconnu", "Point d'accès inconnu.")
                data = route()
            except ServiceError as exc:
                status, data = exc.status, {"code": exc.code, "message": exc.message}
            except Exception as exc:  # noqa: BLE001 — type (et clé courte), jamais le message : il pourrait contenir du texte
                status, data = 500, {"code": "erreur_interne", "message": f"Erreur interne ({error_label(exc)})."}
                # 2.0.0 : le journal dit aussi OÙ (fichiers, lignes, fonctions), sans aucune valeur.
                error = f"erreur interne {error_label(exc)} — {error_location(exc)}"
            # 2.0.0 : le journal est écrit AVANT la réponse (sinon une ligne pouvait manquer quand le client lit
            # le journal juste après avoir reçu la réponse : test instable constaté en exécution parallèle).
            self._log(status, started, error)
            self._send(status, data)

        def do_GET(self):  # noqa: N802
            self._dispatch({"/health": service.health})

        def do_POST(self):  # noqa: N802
            self._dispatch({
                "/translate": lambda: service.translate(self._body()),
                "/index": lambda: {"packages": service.backend.available()},
                "/install": lambda: service.install(self._body()),
                "/install-file": lambda: service.install_file(self._body()),
                "/remove": lambda: service.remove(self._body()),
                "/install-sbd": lambda: service.install_sbd(self._body()),
            })

    return Handler


def make_server(backend, host="0.0.0.0", port=5000):
    return ThreadingHTTPServer((host, port), make_handler(Service(backend)))


def main():
    project = os.environ.get("COMPOSE_PROJECT_CHECK", "")
    # Même règle que docker/entrypoint.sh : un nom réservé n'est accepté que sur autorisation explicite.
    if project in RESERVED_PROJECTS and os.environ.get("AUTORISER_NOM_PROJET", "") != project:
        sys.stderr.write(f"ARRÊT : le projet Docker « {project} » appartient à une installation existante "
                         "(principale ou essai). Corrigez COMPOSE_PROJECT_NAME dans .env, ou ajoutez "
                         f"AUTORISER_NOM_PROJET={project} pour mettre à jour cette installation.\n")
        sys.exit(1)
    port = int(os.environ.get("ARGOS_SERVICE_PORT", "5000"))
    server = make_server(ArgosBackend(os.environ.get("ARGOS_DEPOT_DIR", "/depot")), port=port)
    sys.stderr.write(f"Service Argos prêt sur le port interne {port}.\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
