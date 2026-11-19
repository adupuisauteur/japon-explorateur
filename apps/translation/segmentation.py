"""
Découpage d'un texte en segments (cahier des charges § 4.4).

Garantie absolue : "".join(split_text(t)) == t, pour tout texte. Aucun caractère n'est ajouté, retiré ni
modifié (espaces, retours à la ligne Windows ou Unix compris) : les espaces qui suivent une fin de phrase
sont rattachés au segment qui se termine.

Règles :
- fin de phrase japonaise : 。 ！ ？ ． et leurs équivalents ASCII « ! ? » ; le point ASCII « . » seulement s'il
  est suivi d'un espace puis d'une majuscule, ou de la fin du texte (sources en anglais ; « c. 1716 » ne coupe pas) ;
- une fin de phrase à l'intérieur de guillemets ou de parenthèses (「」『』（）…) ne coupe pas ; la citation
  se termine avec son guillemet fermant (「行く。」 forme un tout) ;
- un retour à la ligne termine le segment, sauf à l'intérieur d'une citation ouverte ; une ligne vide
  termine toujours le segment (paragraphe), même si un guillemet est resté ouvert par erreur ;
- les lectures écrites entre parenthèses, par exemple 漢字（かんじ）, restent dans leur segment.
"""
ENDERS = set("。！？．!?")
OPENERS = {"「": "」", "『": "』", "（": "）", "(": ")", "【": "】", "〈": "〉", "《": "》", "“": "”", "‘": "’", "［": "］"}
CLOSERS = set(OPENERS.values())
SPACES = set(" \t　\r\n")


def split_text(text):
    """Découpe `text` en segments ; la concaténation redonne exactement `text`."""
    if not text:
        return []
    segments, start, depth, i, n = [], 0, 0, 0, len(text)

    def end_at(j):
        """Rattache les fermants, fins de phrase et espaces qui suivent, puis coupe à `j`."""
        nonlocal start, depth
        while j < n and (text[j] in CLOSERS or text[j] in ENDERS):
            if text[j] in CLOSERS:
                depth = max(0, depth - 1)
            j += 1
        while j < n and text[j] in SPACES:
            j += 1
        segments.append(text[start:j])
        start = j
        return j

    while i < n:
        ch = text[i]
        if ch in OPENERS:
            depth += 1
        elif ch in CLOSERS:
            depth = max(0, depth - 1)
            # citation refermée juste après une fin de phrase : la phrase se termine avec le guillemet
            if depth == 0 and i > start and text[i - 1] in ENDERS and _ends_sentence_here(text, i + 1):
                i = end_at(i + 1)
                continue
        if depth == 0 and ch in ENDERS:
            i = end_at(i + 1)
            continue
        if depth == 0 and ch == "." and _ascii_sentence_end(text, i):
            i = end_at(i + 1)
            continue
        if ch == "\n" and (depth == 0 or _blank_line_follows(text, i)):
            depth = 0
            i = end_at(i + 1)
            continue
        i += 1
    if start < n:
        tail = text[start:]
        if segments and not tail.strip():
            segments[-1] += tail
        else:
            segments.append(tail)
    # un premier segment fait seulement d'espaces est rattaché au suivant
    if len(segments) > 1 and not segments[0].strip():
        segments[1] = segments[0] + segments[1]
        segments.pop(0)
    assert "".join(segments) == text  # garantie : jamais de perte ni d'ajout
    return segments


def _ascii_sentence_end(text, i):
    """Point ASCII : fin de phrase s'il est suivi d'espaces puis d'une majuscule (ou de la fin du texte).

    Évite de couper après une abréviation suivie d'un nombre ou d'une minuscule (« c. 1716 », « vol. 2 »).
    """
    j = i + 1
    if j == len(text):
        return True
    if text[j] not in SPACES:
        return False
    while j < len(text) and text[j] in SPACES:
        j += 1
    return j == len(text) or text[j].isupper() or text[j] in OPENERS


def _blank_line_follows(text, i):
    j = i + 1
    while j < len(text) and text[j] in " \t　\r":
        j += 1
    return j < len(text) and text[j] == "\n"


def _ends_sentence_here(text, j):
    """Après 「…。」, la phrase est finie sauf si elle continue (と言った, が, の…) sans ponctuation."""
    while j < len(text) and text[j] in " \t　":
        j += 1
    if j >= len(text) or text[j] in "\r\n" or text[j] in OPENERS:
        return True
    return text[j] not in "とがのはをにもでやへ"


def is_translatable(segment_text):
    """Un segment fait seulement d'espaces ou de ponctuation n'a rien à traduire."""
    return any(ch.isalnum() for ch in segment_text)
