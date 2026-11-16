def help_link(request):
    """Lien « ? » de la barre de menu : page d'aide de l'écran affiché, sinon l'index de l'aide."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    match = getattr(request, "resolver_match", None)
    view_name = match.view_name if match else ""
    if view_name.startswith("help:"):
        return {"help_slug": ""}
    from .pages import page_for_screen

    try:
        return {"help_slug": page_for_screen(view_name) or ""}
    except Exception:  # noqa: BLE001 — une page d'aide mal écrite ne doit jamais casser un écran
        return {"help_slug": ""}
