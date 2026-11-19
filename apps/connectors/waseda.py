"""
Connecteur Waseda Kotenseki Sōgō Database — 早稲田大学図書館 古典籍総合データベース (2.0.0, lot 10).

Accès retenu après l'étude faite sur le poste de l'utilisateur (16/11/2026) :
  - le fonds est distribué par l'API officielle de NDL Search (fournisseur « waseda », recherche et moisson
    ouvertes ; réutilisation des notices libre à des fins non commerciales) : J-ed l'interroge par cette API ;
  - le site de Waseda refuse les requêtes automatiques (robots.txt en 503, archive en 403) : J-ed n'y lit rien et
    se contente de liens vers la page de chaque ouvrage.

Images : toute réutilisation demande l'autorisation de la bibliothèque ; un lien depuis un site à but scientifique
est permis s'il indique « 早稲田大学図書館古典籍総合データベース ». J-ed affiche cette mention avec le lien.
"""
import re

from .ndl import NDLConnector
from .registry import register

PAGE = re.compile(r"https?://www\.wul\.waseda\.ac\.jp/kotenseki/html/[a-z0-9]+/[a-z0-9_]+/?")
RIGHTS = ("Images : 早稲田大学図書館古典籍総合データベース. Toute réutilisation des images demande l'autorisation de "
          "la bibliothèque de l'université Waseda ; le lien depuis un site à but scientifique est permis avec "
          "cette mention. Notice : NDL Search (fournisseur waseda), réutilisation libre à des fins non commerciales.")


@register
class WasedaConnector(NDLConnector):
    key = "waseda"
    label = "Waseda Kotenseki (via NDL Search)"
    description = ("Fonds de livres anciens de la bibliothèque de l'université Waseda, interrogé par l'API officielle "
                   "de NDL Search. Lien vers la page de chaque ouvrage sur le site de Waseda.")
    config_help = {"max_count": "Nombre maximal de résultats par page (défaut 20, maximum 500).",
                   "max_variants": "Nombre de variantes de graphie interrogées en plus du terme principal (défaut 3)."}

    def search(self, query):
        self.config = dict(self.config, extra_params={**(self.config.get("extra_params") or {}), "dpid": "waseda"})
        response = super().search(query)
        for result in response.results:
            links = result.raw.get("seeAlso") or []
            page = next((u for u in links if PAGE.match(u)), "")
            data = result.data
            if page:
                result.raw["ndl_search_url"] = data.get("source_url", "")
                data["source_url"] = page
                data["digital_access_url"] = page
            data["holding_institution_text"] = "早稲田大学図書館"
            data["rights_and_access"] = RIGHTS
        return response
