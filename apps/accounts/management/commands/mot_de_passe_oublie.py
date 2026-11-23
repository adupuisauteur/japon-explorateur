"""2.0.2 — « Mot de passe oublié », pour l'assistant J-ed (poste local, administrateur de l'ordinateur).

J-ed n'envoie pas de courriel : un compte dont le mot de passe est perdu ne peut pas être débloqué depuis la page
de connexion. Cette commande, lancée dans le conteneur par l'assistant (« docker compose exec -T web »), liste les
comptes ou change un mot de passe. Le nouveau mot de passe est lu sur l'entrée standard (jamais en argument : il
n'apparaît ni dans la liste des processus ni dans un journal), vérifié par les règles de mot de passe de J-ed,
et l'action est notée dans le journal des actions sensibles.
"""
import json
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.core.audit import log_action


class Command(BaseCommand):
    help = ("Liste les comptes (--liste) ou change le mot de passe d'un compte (--utilisateur), le nouveau mot de "
            "passe étant lu sur l'entrée standard.")

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--liste", action="store_true", help="Comptes, au format JSON.")
        group.add_argument("--utilisateur", help="Identifiant du compte dont le mot de passe change.")

    def handle(self, *args, **options):
        User = get_user_model()
        if options["liste"]:
            comptes = [
                {"identifiant": u.username, "nom": u.display_name or u.get_full_name(), "role": u.get_role_display(),
                 "actif": u.is_active}
                for u in User.objects.order_by("username")
            ]
            self.stdout.write(json.dumps(comptes, ensure_ascii=False))
            return
        try:
            user = User.objects.get(username=options["utilisateur"])
        except User.DoesNotExist:
            raise CommandError("Compte introuvable.")
        mot = sys.stdin.readline().rstrip("\r\n")
        if not mot:
            raise CommandError("Aucun mot de passe reçu : rien n'a changé.")
        try:
            validate_password(mot, user)
        except ValidationError as erreur:
            raise CommandError("Mot de passe refusé : " + " ".join(erreur.messages))
        user.set_password(mot)
        user.save(update_fields=["password"])
        log_action(None, "accounts.password_reset_local", user,
                   "Mot de passe changé depuis l'assistant J-ed (poste de l'installation)")
        self.stdout.write(f"Mot de passe changé pour « {user.username} ».")
