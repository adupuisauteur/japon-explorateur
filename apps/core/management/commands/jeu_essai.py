"""Jeu d'essai fictif (2.0.0) : `jeu_essai --charger --utilisateur <identifiant>` ou `jeu_essai --retirer`."""
from django.core.management.base import BaseCommand, CommandError

from apps.core import jeu_essai as J


class Command(BaseCommand):
    help = "Charge ou retire le jeu d'essai fictif (notices inventées, un dossier, un projet de traduction)."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--charger", action="store_true")
        group.add_argument("--retirer", action="store_true")
        parser.add_argument("--utilisateur", help="Compte qui recevra le dossier et le projet (défaut : premier "
                                                  "administrateur actif).")

    def handle(self, *args, **opts):
        from apps.accounts.models import User

        if opts["retirer"]:
            summary = J.remove()
            self.stdout.write(f"Jeu d'essai retiré : {summary['notices']} notice(s), {summary['dossiers']} dossier(s), "
                              f"{summary['projets']} projet(s).")
            for kept in summary["gardées"]:
                self.stdout.write(f"  gardé : {kept}")
            return
        users = User.objects.filter(is_active=True)
        user = (users.filter(username=opts["utilisateur"]).first() if opts["utilisateur"]
                else users.filter(role="admin").order_by("pk").first())
        if user is None:
            raise CommandError("Aucun compte correspondant (créez d'abord l'administrateur).")
        summary = J.load(user)
        self.stdout.write(f"Jeu d'essai chargé : {summary['notices']} notice(s) ({summary['créées']} nouvelle(s)), "
                          f"dossier « {summary['dossier']} », projet « {summary['projet']} ».")
