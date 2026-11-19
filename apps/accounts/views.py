from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string

from apps.core.audit import log_action
from apps.core.forms import BootstrapMixin
from apps.core.models import AppSettings
from apps.core.permissions import admin_required

from .forms import FirstRunForm, ProfileForm, UserCreateForm, UserEditForm

User = get_user_model()


def _throttle_key(request, username):
    raw = f"{(username or '').strip().lower()}|{request.META.get('REMOTE_ADDR', '')}"
    return "login-fail:" + hashlib.sha256(raw.encode()).hexdigest()


class LoginView(auth_views.LoginView):
    """Connexion avec verrouillage temporaire après plusieurs échecs (identifiant + adresse IP)."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        key = _throttle_key(request, request.POST.get("username"))
        if cache.get(key, 0) >= settings.LOGIN_MAX_FAILURES:
            form = self.get_form()
            minutes = max(1, settings.LOGIN_LOCKOUT_SECONDS // 60)
            return self.render_to_response(self.get_context_data(
                form=form, locked=True, lock_minutes=minutes), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _throttle_key(self.request, self.request.POST.get("username"))
        try:
            failures = cache.incr(key)
        except ValueError:
            cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
            failures = 1
        else:
            cache.touch(key, settings.LOGIN_LOCKOUT_SECONDS)
        if failures >= settings.LOGIN_MAX_FAILURES:
            log_action(self.request, "auth.lockout", None,
                       f"Connexion verrouillée temporairement après {failures} échecs")
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_throttle_key(self.request, self.request.POST.get("username")))
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs["class"] = "form-control form-control-lg"
        return form


@transaction.atomic
def first_run(request):
    """Assistant de première configuration (§17.1) : disponible uniquement tant qu'aucun compte n'existe."""
    if User.objects.exists():
        return redirect("core:home")
    token_required = bool(settings.SETUP_TOKEN)
    form = FirstRunForm(request.POST or None, token_required=token_required)
    if request.method == "POST" and form.is_valid():
        if token_required and not hmac.compare_digest(form.cleaned_data.get("setup_token", ""), settings.SETUP_TOKEN):
            form.add_error("setup_token", "Jeton de configuration incorrect (valeur SETUP_TOKEN du fichier .env).")
            return render(request, "accounts/first_run.html", {"form": form}, status=403)
        user = form.save(commit=False)
        user.role = User.ROLE_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.display_name = form.cleaned_data["display_name"]
        user.save()
        settings_obj = AppSettings.get()
        settings_obj.default_search_mode = form.cleaned_data["default_search_mode"]
        settings_obj.backup_enabled = form.cleaned_data["backup_enabled"]
        settings_obj.computer_memory_gb = form.cleaned_data.get("computer_memory_gb")
        settings_obj.setup_completed = True
        settings_obj.save()
        from django.core.management import call_command

        call_command("seed_sources", verbosity=0)
        from apps.ai.preferences import active_profile

        active_profile(user)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        log_action(request, "setup.completed", user, "Première configuration effectuée")
        messages.success(request, "Bienvenue ! Les sources ont été répertoriées. Étape suivante conseillée : "
                                  "importer l'inventaire CODH et votre classeur documentaire.")
        if form.cleaned_data.get("install_argos"):
            _first_run_argos(request, user)
        return redirect("updates:import_new")
    return render(request, "accounts/first_run.html", {"form": form})


def _first_run_argos(request, user):
    """2.0.0 (lot 7) : installation de la traduction japonais → français choisie dans l'assistant."""
    from apps.translation import argos_packages as A

    try:
        job = A.prepare_ja_fr(user)
    except A.PackageError as exc:
        messages.warning(request, f"Traduction hors ligne non installée pour l'instant : {exc} Vous pourrez "
                                  "l'installer plus tard dans Traduction → Moteurs locaux.")
        return
    if job is not None:
        log_action(request, "translation.argos_download", job, job.scope_label)
        transaction.on_commit(lambda: A.dispatch(job))
        messages.info(request, "Installation de la traduction japonais → français lancée en arrière-plan : une "
                               "fenêtre vous préviendra à la fin (suivi dans Traduction → Moteurs locaux).")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user, prefix="p")
    pwd = PasswordChangeForm(request.user, request.POST or None, prefix="pw")
    for f in pwd.fields.values():
        f.widget.attrs["class"] = "form-control"
    if request.method == "POST":
        if "save_profile" in request.POST and form.is_valid():
            form.save()
            messages.success(request, "Préférences enregistrées.")
            return redirect("accounts:profile")
        if "change_password" in request.POST and pwd.is_valid():
            pwd.save()
            update_session_auth_hash(request, pwd.user)
            log_action(request, "account.password_changed", request.user)
            messages.success(request, "Mot de passe modifié.")
            return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "pwd": pwd})


@admin_required
def users(request):
    return render(request, "accounts/users.html", {"users": User.objects.order_by("username")})


@admin_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        from apps.ai.preferences import active_profile

        active_profile(user)
        log_action(request, "user.created", user, f"Compte {user.username} ({user.get_role_display()})")
        messages.success(request, "Compte créé.")
        return redirect("accounts:users")
    return render(request, "accounts/user_form.html", {"form": form, "title": "Nouveau compte"})


@admin_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        if target == request.user and (form.cleaned_data["role"] != User.ROLE_ADMIN or not form.cleaned_data["is_active"]):
            messages.error(request, "Vous ne pouvez pas retirer vos propres droits d'administration.")
        else:
            form.save()
            log_action(request, "user.updated", target, f"Rôle : {target.get_role_display()}, actif : {target.is_active}")
            messages.success(request, "Compte mis à jour.")
            return redirect("accounts:users")
    return render(request, "accounts/user_form.html", {"form": form, "title": f"Compte {target.username}", "target": target})


@admin_required
def user_anonymize(request, pk):
    """Suppression des données personnelles d'un compte (§14) : anonymisation, contenus communs conservés."""
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "Impossible d'anonymiser votre propre compte.")
        return redirect("accounts:users")
    if request.method == "POST":
        # 1.3.0 : projets et glossaires de traduction confiés à l'administrateur qui anonymise ; réglages et clés
        # de moteurs effacés.
        # Refusé, sans aucune modification, s'il n'existe aucun autre administrateur actif.
        from apps.translation.ownership import TransferImpossible, release_user_translation_data

        try:
            with transaction.atomic():
                recipient, n_projects, n_glossaries = release_user_translation_data(target, recipient=request.user)
                _anonymize(target)
        except TransferImpossible as exc:
            messages.error(request, str(exc))
            return redirect("accounts:user_edit", pk=target.pk)
        log_action(request, "user.anonymized", target, "Compte anonymisé, données privées supprimées"
                   + (f" ; {n_projects} projet(s) et {n_glossaries} glossaire(s) de traduction confiés à {recipient}"
                      if recipient else ""))
        messages.success(request, "Compte anonymisé ; ses données privées ont été supprimées."
                         + (f" Ses {n_projects} projet(s) et {n_glossaries} glossaire(s) de traduction ont été "
                            f"confiés à {recipient}." if recipient else ""))
        return redirect("accounts:users")
    return render(request, "accounts/user_anonymize.html", {"target": target})


def _anonymize(target):
    """Effacement des données personnelles (traitement inchangé depuis la 1.2.0)."""
    target.username = f"compte-supprime-{get_random_string(8).lower()}"
    target.display_name = "Compte supprimé"
    target.email = target.first_name = target.last_name = ""
    target.is_active = False
    target.set_unusable_password()
    target.save()
    target.ai_credentials.all().delete()
    target.collections.filter(visibility="private").delete()
    target.annotations.filter(visibility="private").delete()
    target.library.all().delete()
    target.search_sessions.all().delete()


class StyledPasswordForm(BootstrapMixin, PasswordChangeForm):
    pass
