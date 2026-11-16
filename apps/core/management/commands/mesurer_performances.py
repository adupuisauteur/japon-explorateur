"""Mesure des performances (2.0.0, lot 9) — voir apps/core/performances.py.

Crée une base PostgreSQL TEMPORAIRE (nom de la base réelle suivi de « _mesures_… »), y place des notices fictives,
mesure, puis la supprime, même en cas d'erreur. La base réelle n'est que lue (transaction annulée).
"""
import json
import os
import subprocess
import sys
from urllib.parse import quote

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core import performances as PERF

MARK_START, MARK_END = "<<<JED-MESURES", "JED-MESURES>>>"


def _url(db, name):
    user = quote(db.get("USER") or "", safe="")
    password = quote(db.get("PASSWORD") or "", safe="")
    auth = f"{user}:{password}@" if password else (f"{user}@" if user else "")
    host = db.get("HOST") or "localhost"
    port = f":{db['PORT']}" if db.get("PORT") else ""
    return f"postgres://{auth}{host}{port}/{name}"


class Command(BaseCommand):
    help = ("Mesure la recherche, les doublons et les principales pages avec des notices fictives dans une base "
            "temporaire (supprimée ensuite), puis la recherche sur vos données en lecture seule.")

    def add_arguments(self, parser):
        parser.add_argument("--notices", type=int, default=50000, help="Notices fictives (défaut : 50 000).")
        parser.add_argument("--essais", type=int, default=5, help="Essais par mesure ; la médiane est retenue.")
        parser.add_argument("--json", action="store_true", help="Sortie JSON.")
        parser.add_argument("--interne", action="store_true", help="(usage interne : dans la base temporaire)")

    def handle(self, *args, **opts):
        count, repetitions = max(100, opts["notices"]), max(1, opts["essais"])
        if opts["interne"]:
            return self._inside(count, repetitions)
        db = settings.DATABASES["default"]
        if "postgresql" not in db.get("ENGINE", ""):
            raise CommandError("Mesure prévue pour PostgreSQL (la base de J-ed sous Docker).")
        report = PERF.Report(notices=count, repetitions=repetitions)
        report.real_count, report.real = PERF.measure_real(repetitions)
        name = f"{db['NAME']}_mesures_{os.getpid()}"[:63]
        if name == db["NAME"]:
            raise CommandError("Nom de base temporaire identique à la base réelle : arrêt.")
        self.stderr.write(f"Base temporaire {name} : création de {count} notices fictives (quelques minutes)…")
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
        try:
            env = dict(os.environ, DATABASE_URL=_url(db, name))
            done = subprocess.run([sys.executable, str(settings.BASE_DIR / "manage.py"), "mesurer_performances",
                                   "--interne", "--notices", str(count), "--essais", str(repetitions)],
                                  env=env, capture_output=True, text=True, timeout=3 * 3600, cwd=str(settings.BASE_DIR))
            out = done.stdout
            if done.returncode != 0 or MARK_START not in out:
                raise CommandError("Mesure dans la base temporaire en échec :\n" + (done.stderr or out)[-2000:])
            data = json.loads(out.split(MARK_START, 1)[1].split(MARK_END, 1)[0])
            report.measures = [PERF.Measure(m["key"], m["label"], m["ms"], m["queries"], m["detail"]) for m in data]
        finally:
            connection.close()
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
            self.stderr.write(f"Base temporaire {name} supprimée.")
        if opts["json"]:
            self.stdout.write(json.dumps(report.as_dict(), ensure_ascii=False, indent=1))
        else:
            self.stdout.write(report.text())

    def _inside(self, count, repetitions):
        db = settings.DATABASES["default"]
        if "_mesures_" not in db.get("NAME", ""):
            raise CommandError("--interne ne s'utilise que dans une base temporaire de mesure.")
        call_command("migrate", verbosity=0, interactive=False)
        user, record = PERF.generate(count)
        measures = PERF.measure_fictive(repetitions, user, record)
        self.stdout.write(MARK_START)
        self.stdout.write(json.dumps([m.__dict__ for m in measures], ensure_ascii=False))
        self.stdout.write(MARK_END)
