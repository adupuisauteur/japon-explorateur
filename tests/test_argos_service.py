"""Évolution 1.3.0 — lot 9 : service Argos Translate facultatif (T6) et gestion des paquets.

Le serveur réel (docker/argos/server.py) est démarré sur la boucle locale avec un traducteur FACTICE :
Argos Translate n'est pas installé dans l'environnement de test et aucun paquet n'est téléchargé.
Les « traductions » factices ne sont que des marques ([ja>en] …) : elles ne prétendent rien traduire.
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from contextlib import redirect_stderr
from pathlib import Path

import httpx
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.incidents.models import Incident
from apps.translation import argos_packages as A
from apps.translation.engines.argos import ArgosEngine
from apps.translation.models import (EngineSetting, TranslationJob, TranslationPreference, TranslationProject,
                                     TranslationVersion)

from .helpers import AppTestCase

ROOT = Path(settings.BASE_DIR)
SPEC = importlib.util.spec_from_file_location("argos_server", ROOT / "docker" / "argos" / "server.py")
server_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server_mod)


class FakeBackend:
    """Remplace argostranslate : paquets en mémoire, « traduction » = marque visible."""

    def __init__(self, depot, installed=(), available=(("ja", "en", "1.1"), ("en", "fr", "1.9"), ("en", "ja", "1.1"))):
        self.depot = Path(depot)
        self.packages = {(a, b): v for a, b, v in installed}
        self.catalog = {(a, b): v for a, b, v in available}
        self.index_reachable = True
        self.no_sbd = set()  # paquets installés sans modèle de découpage en phrases
        self.calls = []

    def version(self):
        return "1.11.0 (factice)"

    def installed(self):
        return [{"from": a, "to": b, "version": v, "name": f"{a} → {b}", "sbd_ready": (a, b) not in self.no_sbd}
                for (a, b), v in sorted(self.packages.items())]

    def available(self):
        self.calls.append("index")
        if not self.index_reachable:
            raise server_mod.ServiceError(502, "index_injoignable", "Index des paquets Argos injoignable (URLError).")
        return [{"from": a, "to": b, "version": v, "name": f"{a} → {b}", "size": 1000} for (a, b), v in self.catalog.items()]

    def install_from_index(self, source, target):
        self.calls.append(f"install {source}→{target}")
        if not self.index_reachable:
            raise server_mod.ServiceError(502, "index_injoignable", "Index des paquets Argos injoignable (URLError).")
        if (source, target) not in self.catalog:
            raise server_mod.ServiceError(404, "paquet_absent", "absent")
        self.packages[(source, target)] = self.catalog[(source, target)]
        return {"from": source, "to": target, "version": self.catalog[(source, target)]}

    def install_from_file(self, filename):
        if not server_mod.FILENAME.match(filename or ""):
            raise server_mod.ServiceError(400, "fichier_refuse", "Nom de fichier refusé.")
        path = self.depot / filename
        if not path.is_file():
            raise server_mod.ServiceError(404, "fichier_absent", "Fichier introuvable.")
        with zipfile.ZipFile(path) as z:
            meta = json.loads(z.read("metadata.json"))
        self.packages[(meta["from_code"], meta["to_code"])] = meta["package_version"]
        return {"installed": filename}

    def install_sbd(self, source, target):
        self.calls.append(f"sbd {source}→{target}")
        if (source, target) not in self.packages:
            raise server_mod.ServiceError(404, "paquet_absent", "absent")
        had = (source, target) in self.no_sbd
        self.no_sbd.discard((source, target))
        return {"sbd_model": "en" if had else ""}

    def remove(self, source, target):
        if (source, target) not in self.packages:
            raise server_mod.ServiceError(404, "paquet_absent", "absent")
        del self.packages[(source, target)]
        return {"removed": f"{source}→{target}"}

    def translate_step(self, texts, source, target):
        if any("ERREUR" in t for t in texts):
            raise RuntimeError("message interne contenant un texte secret")
        return [f"[{source}>{target}] {t}" for t in texts]


class ServerMixin:
    """Démarre le vrai serveur HTTP du service sur un port libre de la boucle locale."""

    def start_server(self, **backend_kwargs):
        self.depot = Path(tempfile.mkdtemp(prefix="argos-depot-"))
        self.addCleanup(shutil.rmtree, self.depot, ignore_errors=True)
        self.backend = FakeBackend(self.depot, **backend_kwargs)
        self.server = server_mod.make_server(self.backend, host="127.0.0.1", port=0)
        self.log = io.StringIO()
        thread = threading.Thread(target=self._serve, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _serve(self):
        with redirect_stderr(self.log):
            self.server.serve_forever()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())


# --------------------------------------------------------------------------- serveur


class ServerTests(ServerMixin, SimpleTestCase):
    def setUp(self):
        self.start_server(installed=(("ja", "en", "1.1"), ("en", "fr", "1.9")))

    def test_health_lists_packages(self):
        status, data = self.call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["argos_version"], "1.11.0 (factice)")
        self.assertEqual([(p["from"], p["to"], p["version"]) for p in data["packages"]],
                         [("en", "fr", "1.9"), ("ja", "en", "1.1")])
        self.assertFalse(data["busy"])

    def test_translate_through_english_pivot(self):
        status, data = self.call("POST", "/translate", {"texts": ["文A", "文B"], "source": "ja", "target": "fr"})
        self.assertEqual(status, 200)
        self.assertEqual(data["path"], ["ja", "en", "fr"])
        self.assertEqual(data["translations"], ["[en>fr] [ja>en] 文A", "[en>fr] [ja>en] 文B"])
        status, data = self.call("POST", "/translate", {"texts": ["x"], "source": "en", "target": "fr"})
        self.assertEqual(data["path"], ["en", "fr"])

    def test_missing_package_bad_pair_and_bad_requests(self):
        self.backend.packages.pop(("ja", "en"))
        status, data = self.call("POST", "/translate", {"texts": ["文"], "source": "ja", "target": "fr"})
        self.assertEqual((status, data["code"]), (404, "paquet_absent"))
        status, data = self.call("POST", "/translate", {"texts": ["x"], "source": "de", "target": "fr"})
        self.assertEqual((status, data["code"]), (400, "langue_non_prise"))
        status, data = self.call("POST", "/translate", {"texts": "pas une liste", "source": "en", "target": "fr"})
        self.assertEqual(status, 400)
        self.assertEqual(self.call("GET", "/inconnu")[0], 404)

    def test_log_and_errors_never_contain_text(self):
        self.call("POST", "/translate", {"texts": ["秘密の文"], "source": "en", "target": "fr"})
        status, data = self.call("POST", "/translate", {"texts": ["ERREUR 秘密"], "source": "en", "target": "fr"})
        self.assertEqual((status, data["code"]), (500, "erreur_interne"))
        self.assertNotIn("secret", data["message"])
        log = self.log.getvalue()
        self.assertIn("POST /translate 200", log)
        self.assertNotIn("秘密", log)

    def test_one_installation_at_a_time(self):
        svc = server_mod.Service(self.backend)
        svc.install_lock.acquire()
        with self.assertRaises(server_mod.ServiceError) as ctx:
            svc.install({"from": "en", "to": "ja"})
        self.assertEqual(ctx.exception.status, 409)
        svc.install_lock.release()
        self.assertEqual(svc.install({"from": "en", "to": "ja"})["version"], "1.1")

    def test_file_names_are_checked(self):
        for name in ("../etc/passwd", "paquet.zip", "a/b.argosmodel", ""):
            with self.subTest(name=name):
                status, data = self.call("POST", "/install-file", {"filename": name})
                self.assertEqual((status, data["code"]), (400, "fichier_refuse"))

    def test_remove(self):
        status, _ = self.call("POST", "/remove", {"from": "en", "to": "fr"})
        self.assertEqual(status, 200)
        self.assertEqual(self.call("POST", "/remove", {"from": "en", "to": "fr"})[1]["code"], "paquet_absent")

    def test_reserved_project_names_refuse_to_start(self):
        for name in ("japon-explorateur", "japon-explorateur-essai"):
            with self.subTest(name=name):
                result = subprocess.run(["python3", str(ROOT / "docker" / "argos" / "server.py")],
                                        env=dict(os.environ, COMPOSE_PROJECT_CHECK=name), capture_output=True,
                                        text=True, timeout=30)
                self.assertEqual(result.returncode, 1)
                self.assertIn("ARRÊT", result.stderr)


# --------------------------------------------------------------------------- client et moteur


class ClientMixin(ServerMixin):
    def connect(self, **backend_kwargs):
        self.start_server(**backend_kwargs)
        ArgosEngine.transport = httpx.HTTPTransport()  # boucle locale uniquement (serveur de test)
        self.addCleanup(setattr, ArgosEngine, "transport", None)
        override = override_settings(TRANSLATION_ARGOS_URL=self.url, TRANSLATION_ARGOS_DEPOT_DIR=self.depot)
        override.enable()
        self.addCleanup(override.disable)


class EngineTests(ClientMixin, AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.researcher
        self.client.force_login(self.owner)
        EngineSetting.objects.create(user=self.owner, engine="argos", enabled=True)
        TranslationPreference.objects.create(user=self.owner, default_engine="argos", migrated_from_ai=True)

    def engine(self):
        return ArgosEngine(self.owner, setting=EngineSetting.objects.get(user=self.owner, engine="argos"))

    def test_service_absent_means_simulation(self):
        with override_settings(TRANSLATION_ARGOS_URL=""):
            status = self.engine().status()
        self.assertTrue(status.simulated)
        self.assertIn("non activé", status.detail)
        with override_settings(TRANSLATION_ARGOS_URL="http://127.0.0.1:9"):  # port fermé
            ArgosEngine.transport = httpx.HTTPTransport()
            self.addCleanup(setattr, ArgosEngine, "transport", None)
            status = self.engine().status()
        self.assertTrue(status.simulated)
        self.assertIn("hors-ligne", status.detail)

    def test_package_missing_means_simulation(self):
        self.connect(installed=(("en", "fr", "1.9"),))
        status = self.engine().status()
        self.assertTrue(status.simulated)
        self.assertIn("paquets de langues nécessaires non installés", status.detail)

    def test_package_without_sentence_model_means_simulation(self):
        self.connect(installed=(("ja", "en", "1.1"), ("en", "fr", "1.9")))
        self.backend.no_sbd.add(("ja", "en"))
        status = self.engine().status()
        self.assertTrue(status.simulated)
        self.assertIn("modèle de découpage en phrases manquant", status.detail)

    def test_real_translation_records_package_versions(self):
        self.connect(installed=(("ja", "en", "1.1"), ("en", "fr", "1.9")))
        self.assertEqual(self.engine().status().label, "Disponible hors ligne")
        project = TranslationProject.objects.create(owner=self.owner, title="Projet hors ligne", confidential=True)
        self.client.post(f"/traduction/projets/{project.pk}/documents/nouveau/",
                         {"title": "Doc", "variety": "modern", "text": "一つ目の文。"})
        document = project.documents.get()
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {"scope": "untranslated", "action": "translate",
                                                                       "engine": "default"})
        job = TranslationJob.objects.latest("pk")
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm"})
        version = TranslationVersion.objects.get(segment__document=document)
        self.assertFalse(version.simulated)
        self.assertEqual(version.text, "[en>fr] [ja>en] 一つ目の文。")
        self.assertEqual(version.engine_version, "Argos 1.11.0 (factice) — ja→en 1.1 ; en→fr 1.9")


# --------------------------------------------------------------------------- paquets


def argosmodel(source="en", target="fr", version="1.9"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("metadata.json", json.dumps({"from_code": source, "to_code": target, "package_version": version}))
    return buffer.getvalue()


class PackageTests(ClientMixin, AppTestCase):
    def test_page_for_researcher_and_admin(self):
        self.connect()
        self.client.force_login(self.researcher)
        page = self.client.get("/traduction/moteurs/locaux/")
        self.assertContains(page, "En service")
        self.assertContains(page, "seul un administrateur")
        self.assertNotContains(page, "Consulter l'index Argos")
        self.assertEqual(self.client.post("/traduction/moteurs/locaux/telecharger/",
                                          {"packages": ["ja→en"], "confirm": "1"}).status_code, 403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/traduction/moteurs/locaux/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/traduction/moteurs/locaux/"), "Consulter l'index Argos")

    def test_nothing_is_downloaded_without_explicit_choice(self):
        self.connect()
        page = self.client.get("/traduction/moteurs/locaux/")  # affichage : le service local seulement
        self.assertEqual(page.status_code, 200)
        self.assertEqual(self.backend.calls, [])
        index = self.client.post("/traduction/moteurs/locaux/index/")  # consultation : liste, aucun téléchargement
        self.assertContains(index, "ja→en")
        self.assertContains(index, 'value="ja→en" id="p-')
        self.assertEqual(self.backend.calls, ["index"])
        self.client.post("/traduction/moteurs/locaux/telecharger/", {"packages": ["ja→en", "en→fr"]})  # sans case
        self.assertEqual(self.backend.calls, ["index"])
        self.assertFalse(TranslationJob.objects.filter(kind="package").exists())

    def test_download_job_is_tracked_and_resumable(self):
        self.connect(installed=(("en", "fr", "1.9"),))
        self.client.post("/traduction/moteurs/locaux/telecharger/",
                         {"packages": ["ja→en", "en→fr"], "confirm": "1"})
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual((job.status, job.done_items), ("done", 2))
        details = dict(job.items.values_list("record_field", "error_message"))
        self.assertEqual(details, {"index:ja→en": "version 1.1", "index:en→fr": "déjà installé"})
        self.assertEqual(self.backend.calls, ["install ja→en"])  # le paquet présent n'est pas retéléchargé
        # les installations n'apparaissent pas parmi les tâches de traduction
        self.assertNotContains(self.client.get("/traduction/taches/"), f"/traduction/taches/{job.pk}/")
        self.assertEqual(self.client.get(f"/traduction/taches/{job.pk}/").status_code, 404)

    def test_failure_is_reported_then_relaunched(self):
        self.connect()
        self.backend.index_reachable = False
        self.client.post("/traduction/moteurs/locaux/telecharger/", {"packages": ["ja→en"], "confirm": "1"})
        job = TranslationJob.objects.get(kind="package")
        item = job.items.get()
        self.assertEqual((job.status, item.status), ("failed", "failed"))
        self.assertIn("injoignable", item.error_message)
        self.assertTrue(Incident.objects.filter(module="traduction").exists())
        self.assertContains(self.client.get("/traduction/moteurs/locaux/"), "Reprendre")
        self.backend.index_reachable = True
        self.client.post(f"/traduction/moteurs/locaux/taches/{job.pk}/", {"action": "relaunch"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertIn(("ja", "en"), self.backend.packages)

    def test_install_from_file_without_internet(self):
        self.connect()
        upload = SimpleUploadedFile("translate-en_fr-1_9.argosmodel", argosmodel())
        self.client.post("/traduction/moteurs/locaux/fichier/", {"file": upload})
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual(job.status, "done", job.items.get().error_message)
        self.assertEqual(self.backend.packages, {("en", "fr"): "1.9"})
        self.assertEqual(list(self.depot.iterdir()), [])  # copie de transfert effacée après installation
        self.assertEqual(self.backend.calls, [])  # aucun appel à l'index

    def test_sentence_model_download_on_explicit_choice(self):
        self.connect(installed=(("ja", "en", "1.1"),))
        self.backend.no_sbd.add(("ja", "en"))
        self.assertContains(self.client.get("/traduction/moteurs/locaux/"), "modèle de découpage en phrases manquant")
        self.client.post("/traduction/moteurs/locaux/decoupage/", {"package": "ja→en"})  # sans confirmation
        self.assertEqual(self.backend.calls, [])
        self.client.post("/traduction/moteurs/locaux/decoupage/", {"package": "ja→en", "confirm": "1"})
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual((job.status, job.items.get().error_message), ("done", "modèle « en » téléchargé"))
        self.assertEqual(self.backend.no_sbd, set())

    def test_bad_files_are_refused(self):
        self.connect()
        for name, content in (("paquet.zip", argosmodel()), ("faux.argosmodel", b"pas une archive")):
            with self.subTest(name=name):
                response = self.client.post("/traduction/moteurs/locaux/fichier/",
                                            {"file": SimpleUploadedFile(name, content)}, follow=True)
                self.assertContains(response, "Fichier refusé")
        self.assertFalse(TranslationJob.objects.filter(kind="package").exists())

    def test_remove_package(self):
        self.connect(installed=(("en", "fr", "1.9"),))
        self.client.post("/traduction/moteurs/locaux/desinstaller/", {"package": "en→fr"})
        self.assertEqual(self.backend.packages, {})
        response = self.client.post("/traduction/moteurs/locaux/desinstaller/", {"package": "../x"}, follow=True)
        self.assertContains(response, "non pris en charge")

    def test_stale_job_detection(self):
        from datetime import timedelta

        from django.utils import timezone

        job = TranslationJob.objects.create(user=self.admin, kind="package", engine="argos", status="running",
                                            heartbeat_at=timezone.now() - timedelta(hours=2))
        self.assertTrue(A.is_stale(job))
        job.heartbeat_at = timezone.now()
        self.assertFalse(A.is_stale(job))


# --------------------------------------------------------------------------- moteur Argos réel (bibliothèque factice)


class FakeArgosLibrary:
    """Imite l'interface d'argostranslate 1.11.0, minisbd et stanza (lue dans leur code source)."""

    def __init__(self, root):
        import sys
        import types

        self.root = Path(root)
        self.downloads = self.root / "downloads"
        self.cache = self.root / "minisbd"
        self.downloads.mkdir()
        self.cache.mkdir()
        self.installed, self.network = [], []
        lib = self

        class Pkg:
            def __init__(self, a, b, version, sbd=None, type="translate"):
                self.from_code, self.to_code, self.package_version = a, b, version
                self.from_name, self.to_name, self.type, self.packaged_sbd_path = a, b, type, sbd

        class Available(Pkg):
            def download(self):
                lib.network.append(f"paquet {self.from_code}→{self.to_code}")
                path = lib.downloads / f"translate-{self.from_code}_{self.to_code}.argosmodel"
                path.write_bytes(b"PK")
                return path

        self.Pkg, self.Available = Pkg, Available
        package = types.ModuleType("argostranslate.package")
        package.update_package_index = lambda: lib.network.append("index")
        package.get_available_packages = lambda: [Available("ja", "en", "1.0"), Available("ja", "en", "1.1"),
                                                  Available("en", "fr", "1.9"), Available("de", "fr", "1.0"),
                                                  Available("en", "en", "1", type="sbd")]
        package.get_installed_packages = lambda: list(lib.installed)
        package.install_from_path = lambda path: lib.installed.append(Pkg("ja", "en", "1.1"))
        package.uninstall = lambda pkg: lib.installed.remove(pkg)
        translate = types.ModuleType("argostranslate.translate")
        translate.translate = lambda q, a, b: f"<{a}{b}>{q}"
        sbd = types.ModuleType("argostranslate.sbd")

        class MiniSBDSentencizer:
            LANGUAGE_CODE_MAPPING = {"zh": "zh-hans"}

        sbd.MiniSBDSentencizer = MiniSBDSentencizer
        root_mod = types.ModuleType("argostranslate")
        root_mod.package, root_mod.translate, root_mod.sbd = package, translate, sbd
        minisbd = types.ModuleType("minisbd")
        models = types.ModuleType("minisbd.models")
        models.MODELS = {"en": "en.onnx", "fr": "fr.onnx"}
        models.list_models = lambda: list(models.MODELS)
        models.cache_dir = str(self.cache)

        def get_model_file(name):
            lib.network.append(f"minisbd {name}")
            (lib.cache / models.MODELS[name]).write_bytes(b"onnx")
            return str(lib.cache / models.MODELS[name])

        models.get_model_file = get_model_file
        minisbd.models = models
        stanza = types.ModuleType("stanza")
        stanza.Pipeline = lambda *a, **kw: kw
        self.stanza = stanza
        self.modules = {"argostranslate": root_mod, "argostranslate.package": package,
                        "argostranslate.translate": translate, "argostranslate.sbd": sbd, "minisbd": minisbd,
                        "minisbd.models": models, "stanza": stanza}
        self.saved = {name: sys.modules.get(name) for name in self.modules}
        sys.modules.update(self.modules)

    def restore(self):
        import sys

        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class RealBackendTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="argos-lib-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lib = FakeArgosLibrary(self.tmp)
        self.addCleanup(self.lib.restore)
        self.backend = server_mod.ArgosBackend(self.tmp)

    def test_install_from_index_picks_latest_version_cleans_download_and_prepares_sentence_model(self):
        result = self.backend.install_from_index("ja", "en")
        self.assertEqual(result["version"], "1.1")
        self.assertEqual(result["sbd_model"], "en")  # pas de modèle MiniSBD japonais : repli anglais d'Argos
        self.assertEqual(self.lib.network, ["index", "paquet ja→en", "minisbd en"])
        self.assertEqual(list(self.lib.downloads.iterdir()), [])  # fichier téléchargé effacé après installation
        self.assertTrue(self.backend.installed()[0]["sbd_ready"])

    def test_translation_never_downloads(self):
        self.lib.installed.append(self.lib.Pkg("ja", "en", "1.1"))  # sans modèle de découpage
        self.assertFalse(self.backend.installed()[0]["sbd_ready"])
        with self.assertRaises(server_mod.ServiceError) as ctx:
            self.backend.translate_step(["文"], "ja", "en")
        self.assertEqual(ctx.exception.code, "sbd_absent")
        self.assertEqual(self.lib.network, [])
        self.assertEqual(self.backend.install_sbd("ja", "en"), {"sbd_model": "en"})  # choix explicite
        self.assertEqual(self.backend.translate_step(["文"], "ja", "en"), ["<jaen>文"])
        self.assertEqual(self.lib.network, ["minisbd en"])

    def test_package_with_embedded_model_and_offline_stanza(self):
        self.lib.installed.append(self.lib.Pkg("en", "fr", "1.9", sbd=self.tmp / "stanza"))
        self.assertTrue(self.backend.installed()[0]["sbd_ready"])
        self.backend.translate_step(["x"], "en", "fr")
        self.assertEqual(self.lib.stanza.Pipeline(lang="en"), {"lang": "en", "download_method": None})

    def test_index_lists_only_module_languages_and_translation_packages(self):
        codes = [(p["from"], p["to"]) for p in self.backend.available()]
        self.assertEqual(codes, [("ja", "en"), ("ja", "en"), ("en", "fr")])

    def test_install_from_file_stays_in_depot(self):
        (self.tmp / "ok.argosmodel").write_bytes(b"PK")
        self.assertEqual(self.backend.install_from_file("ok.argosmodel"), {"installed": "ok.argosmodel"})
        self.assertEqual(self.lib.network, [])  # aucun appel réseau, pas même pour le modèle de découpage
        with self.assertRaises(server_mod.ServiceError):
            self.backend.install_from_file("../ok.argosmodel")


# --------------------------------------------------------------------------- fichiers livrés


def read(name):
    return (ROOT / name).read_text(encoding="utf-8-sig")


class DeliveryTests(SimpleTestCase):
    def compose_config(self, *profile):
        if shutil.which("docker") is None:
            self.skipTest("Docker Compose absent")
        tmp = Path(tempfile.mkdtemp(prefix="compose-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(ROOT / "docker-compose.yml", tmp)
        (tmp / ".env").write_text("")
        args = ["docker", "compose", *(["--profile", profile[0]] if profile else []), "config", "--format", "json"]
        result = subprocess.run(args, cwd=tmp, capture_output=True, text=True, timeout=60,
                                env=dict(os.environ, POSTGRES_PASSWORD="fictif-pour-test"))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_compose_without_profile_has_no_argos(self):
        config = self.compose_config()
        self.assertNotIn("argos", config["services"])
        self.assertEqual(config["services"]["web"]["environment"]["TRANSLATION_ARGOS_URL"], "http://argos:5000")

    def test_compose_with_profile_argos_is_internal_only(self):
        config = self.compose_config("hors-ligne")
        argos = config["services"]["argos"]
        self.assertNotIn("ports", argos)  # aucun port publié
        self.assertEqual(argos["image"], "japon-explorateur-argos:1.3.0")
        mounts = {v["source"]: v for v in argos["volumes"]}
        self.assertEqual(mounts["argos-packages"]["target"], "/argos")
        self.assertTrue(mounts["argos-depot"]["read_only"])
        self.assertEqual(argos["environment"]["COMPOSE_PROJECT_CHECK"], "japon-explorateur-essai-130")
        self.assertIn("argos-packages", config["volumes"])

    def test_argos_dependencies_are_pinned_and_cpu_only(self):
        lines = [l for l in read("docker/argos/requirements.txt").splitlines() if l and not l.startswith("#")]
        self.assertTrue(all("==" in l for l in lines))
        self.assertIn("argostranslate==1.11.0", lines)
        self.assertIn("torch==2.5.1+cpu", lines)
        self.assertFalse([l for l in lines if l.startswith(("nvidia-", "triton"))])
        dockerfile = read("docker/argos/Dockerfile")
        self.assertIn("--extra-index-url https://download.pytorch.org/whl/cpu", dockerfile)
        self.assertIn("HF_HUB_OFFLINE=1", dockerfile)
        app = read("requirements.txt").lower()
        self.assertNotIn("argostranslate", app)
        self.assertNotIn("torch", app)

    def test_reset_script_keeps_argos_packages_unless_complete(self):
        script = read("reinitialiser-essai.ps1")
        self.assertNotIn("down -v", script)
        self.assertIn("& docker compose --profile hors-ligne down --remove-orphans", script)
        self.assertIn("$SuffixePaquets = '_argos-packages'", script)
        self.assertIn('$aEffacer = @($volumes | Where-Object { $_ -ne "${Projet}${SuffixePaquets}" })', script)
        self.assertIn("japon-explorateur-argos:$Version", script)
        self.assertIn("& docker compose --profile hors-ligne up -d --build", script)
