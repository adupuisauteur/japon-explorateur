"""2.0.2, lot 3 — commande « mot_de_passe_oublie » utilisée par l'assistant J-ed."""
import io
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.models import AuditLog


class MotDePasseOublieTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("auteur-fictif", password="ancien-mot-de-passe-41")

    def run_cmd(self, *args, stdin=""):
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)):
            call_command("mot_de_passe_oublie", *args, stdout=out)
        return out.getvalue()

    def test_lists_accounts_as_json(self):
        comptes = json.loads(self.run_cmd("--liste"))
        self.assertEqual([c["identifiant"] for c in comptes], ["auteur-fictif"])
        self.assertTrue(comptes[0]["actif"])

    def test_changes_the_password_read_from_stdin_and_logs_it(self):
        out = self.run_cmd("--utilisateur", "auteur-fictif", stdin="Nouveau-Mot-De-Passe-2026\n")
        self.assertIn("Mot de passe changé", out)
        self.assertNotIn("Nouveau-Mot-De-Passe-2026", out)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nouveau-Mot-De-Passe-2026"))
        log = AuditLog.objects.get(action="accounts.password_reset_local")
        self.assertNotIn("Nouveau-Mot-De-Passe-2026", json.dumps(log.details) + log.summary)

    def test_weak_or_missing_password_changes_nothing(self):
        for mot in ("123", "", "motdepasse"):
            with self.assertRaises(CommandError):
                self.run_cmd("--utilisateur", "auteur-fictif", stdin=mot + "\n")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ancien-mot-de-passe-41"))

    def test_unknown_account(self):
        with self.assertRaises(CommandError):
            self.run_cmd("--utilisateur", "personne", stdin="Nouveau-Mot-De-Passe-2026\n")
