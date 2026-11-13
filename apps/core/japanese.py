"""
Outils déterministes pour les écritures japonaises.

Toutes les fonctions ci-dessous produisent des formes *dérivées* : elles ne
remplacent jamais la graphie source, qui reste stockée telle quelle (§6.5).
"""
import functools
import re
import unicodedata

# --------------------------------------------------------------------------- Unicode


def nfc(text):
    return unicodedata.normalize("NFC", text or "")


def nfkc(text):
    return unicodedata.normalize("NFKC", text or "")


MACRONS = str.maketrans({
    "ā": "a", "ī": "i", "ū": "u", "ē": "e", "ō": "o", "â": "a", "î": "i", "û": "u", "ê": "e", "ô": "o",
    "Ā": "A", "Ī": "I", "Ū": "U", "Ē": "E", "Ō": "O", "Â": "A", "Î": "I", "Û": "U", "Ê": "E", "Ô": "O",
})


def fold_macrons(text):
    return (text or "").translate(MACRONS)


def kata_to_hira(text):
    out = []
    for ch in text or "":
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def hira_to_kata(text):
    out = []
    for ch in text or "":
        code = ord(ch)
        if 0x3041 <= code <= 0x3096:
            out.append(chr(code + 0x60))
        else:
            out.append(ch)
    return "".join(out)


_JA_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")
_KANJI_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_KANA_RE = re.compile(r"[぀-ヿ]")


def has_japanese(text):
    return bool(_JA_RE.search(text or ""))


def has_kanji(text):
    return bool(_KANJI_RE.search(text or ""))


def is_kana_only(text):
    t = re.sub(r"[\s・ー]", "", text or "")
    return bool(t) and all(_KANA_RE.match(c) for c in t)


def search_normalize(text):
    """Forme de comparaison : NFKC, minuscules, macrons repliés, katakana → hiragana.

    Normalisation documentée et réversible au sens où la forme source reste stockée.
    Les variantes de kanji (anciennes/nouvelles formes) ne sont PAS repliées : elles
    sont proposées comme suggestions (§7.3).
    """
    t = nfkc(text).lower()
    t = fold_macrons(t)
    t = kata_to_hira(t)
    t = re.sub(r"[\s　]+", " ", t)
    return t.strip()


# --------------------------------------------------------------------------- lectures et rōmaji


@functools.lru_cache(maxsize=1)
def _kakasi():
    try:
        import pykakasi

        return pykakasi.kakasi()
    except Exception:  # pragma: no cover - dépendance absente
        return None


@functools.lru_cache(maxsize=4096)
def _convert(text):
    k = _kakasi()
    if k is None or not text:
        return ()
    return tuple((item["orig"], item["hira"], item["hepburn"]) for item in k.convert(text))


def to_romaji(text):
    """Rōmaji automatique (Hepburn, via pykakasi). Lecture NON vérifiée pour les kanji."""
    parts = [hep for orig, hira, hep in _convert(nfkc(text)) if hep.strip()]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def to_hiragana_reading(text):
    """Lecture automatique en hiragana (non vérifiée pour les kanji)."""
    return "".join(hira for orig, hira, hep in _convert(nfkc(text)))


_ROMA = {
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ", "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "chi": "ち",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "tsu": "つ", "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ", "mya": "みゃ", "myu": "みゅ", "myo": "みょ", "rya": "りゃ",
    "ryu": "りゅ", "ryo": "りょ", "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ", "ja": "じゃ", "ju": "じゅ",
    "jo": "じょ", "bya": "びゃ", "byu": "びゅ", "byo": "びょ", "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "shi": "し", "ji": "じ", "fu": "ふ", "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "su": "す", "se": "せ", "so": "そ", "ta": "た", "te": "て", "to": "と", "na": "な",
    "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の", "ha": "は", "hi": "ひ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も", "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ", "wa": "わ", "wo": "を", "ga": "が",
    "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご", "za": "ざ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど", "ba": "ば", "bi": "び", "bu": "ぶ",
    "be": "べ", "bo": "ぼ", "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ", "si": "し",
    "ti": "ち", "tu": "つ", "hu": "ふ", "zi": "じ", "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
}
_ROMA_KEYS = sorted(_ROMA, key=len, reverse=True)
_LONG_VOWELS = {"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ei", "ō": "ou", "â": "aa", "î": "ii", "û": "uu",
                "ê": "ei", "ô": "ou"}


def romaji_to_hiragana(text):
    """Conversion rōmaji (Hepburn) → hiragana. Renvoie '' si la chaîne n'est pas convertible."""
    t = nfkc(text).lower()
    for k, v in _LONG_VOWELS.items():
        t = t.replace(k, v)
    t = t.replace("'", "").replace("-", "")
    out, i = [], 0
    while i < len(t):
        ch = t[i]
        if ch == " ":
            out.append(" ")
            i += 1
            continue
        if ch == "n" and (i + 1 == len(t) or t[i + 1] not in "aiueoy"):
            out.append("ん")
            i += 1
            continue
        if ch == "m" and i + 1 < len(t) and t[i + 1] in "bmp":
            out.append("ん")
            i += 1
            continue
        if i + 1 < len(t) and ch == t[i + 1] and ch not in "aiueon":
            out.append("っ")
            i += 1
            continue
        if ch == "t" and t[i + 1:i + 3] == "ch":
            out.append("っ")
            i += 1
            continue
        for key in _ROMA_KEYS:
            if t.startswith(key, i):
                out.append(_ROMA[key])
                i += len(key)
                break
        else:
            return ""
    return "".join(out)


def looks_like_romaji(text):
    t = fold_macrons(nfkc(text)).lower().strip()
    return bool(t) and bool(re.fullmatch(r"[a-z' \-]+", t)) and romaji_to_hiragana(text) != ""


# --------------------------------------------------------------------------- anciennes / nouvelles formes de kanji
# Sélection de correspondances kyūjitai ↔ shinjitai fréquentes dans les titres anciens.
KYUJITAI_PAIRS = (
    "國国 學学 會会 體体 氣気 聲声 寫写 圖図 舊旧 實実 傳伝 譯訳 歷歴 曆暦 禮礼 藝芸 廣広 齋斎 齊斉 "
    "應応 戰戦 鬪闘 將将 獨独 縣県 鐵鉄 澤沢 濱浜 邊辺 邉辺 關関 齒歯 龍竜 靈霊 佛仏 經経 釋釈 "
    "輕軽 樂楽 數数 單単 嚴厳 聽聴 廳庁 擧挙 舉挙 檢検 驗験 險険 權権 歡歓 觀観 勸勧 鹽塩 圓円 "
    "壽寿 卷巻 戀恋 變変 蠻蛮 灣湾 爭争 當当 黨党 對対 帶帯 滯滞 稱称 彈弾 晝昼 盡尽 獻献 "
    "櫻桜 營営 榮栄 螢蛍 勞労 發発 廢廃 參参 惠恵 德徳 眞真 愼慎 縱縦 從従 處処 繪絵 繼継 斷断 "
    "續続 讀読 賣売 寶宝 豐豊 萬万 與与 譽誉 豫予 臺台 來来 亂乱 兩両 號号 濟済 劍剣 劒剣 藏蔵 "
    "臟臓 莊荘 裝装 壯壮 狀状 屬属 嶽岳 岳岳 據拠 歸帰 鄕郷 鄉郷 價価 假仮 拂払 拜拝 埀垂 曉暁 "
    "姬姫 兒児 惡悪 壓圧 圍囲 醫医 爲為 隱隠 驛駅 鹽塩 奧奥 溫温 價価 畫画 擴拡 覺覚 嶽岳 "
    "樣様 搖揺 謠謡 遙遥 欄欄 覽覧 戾戻 祕秘 碎砕 雜雑 濕湿 收収 澁渋 肅粛 敍叙 燒焼 證証 疊畳 "
    "孃嬢 讓譲 釀醸 觸触 寢寝 愼慎 粹粋 醉酔 穗穂 隨随 髓髄 樞枢 攝摂 竊窃 專専 淺浅 錢銭 潛潜 "
    "纖繊 禪禅 雙双 搜捜 插挿 巢巣 總総 騷騒 增増 憎憎 贈贈 臧蔵 卽即 續続 墮堕 對対 臺台 瀧滝 "
    "擇択 澤沢 擔担 膽胆 團団 遲遅 癡痴 蟲虫 晝昼 鑄鋳 廳庁 徵徴 聽聴 鎭鎮 轉転 點点 傳伝 燈灯 "
    "盜盗 稻稲 德徳 讀読 屆届 貳弐 惱悩 腦脳 霸覇 廢廃 賣売 麥麦 發発 髮髪 拔抜 蠻蛮 祕秘 濱浜 "
    "甁瓶 拂払 佛仏 竝並 變変 邊辺 辨弁 瓣弁 辯弁 舖舗 步歩 穗穂 寶宝 豐豊 襃褒 飜翻 每毎 萬万 "
    "滿満 默黙 譯訳 藥薬 與与 譽誉 搖揺 樣様 謠謡 來来 賴頼 亂乱 覽覧 龍竜 兩両 獵猟 綠緑 壘塁 "
    "淚涙 勵励 禮礼 靈霊 齡齢 戀恋 爐炉 勞労 樓楼 錄録 灣湾 繩縄 鷄鶏"
)
OLD_TO_NEW = {}
NEW_TO_OLD = {}
for _pair in KYUJITAI_PAIRS.split():
    if len(_pair) == 2 and _pair[0] != _pair[1]:
        OLD_TO_NEW[_pair[0]] = _pair[1]
        NEW_TO_OLD.setdefault(_pair[1], _pair[0])


def to_shinjitai(text):
    return "".join(OLD_TO_NEW.get(c, c) for c in text or "")


def to_kyujitai(text):
    return "".join(NEW_TO_OLD.get(c, c) for c in text or "")


# --------------------------------------------------------------------------- ères (元号) et dates

# Année grégorienne de début de chaque ère (règle : an 1 de l'ère = année de début).
ERAS = {
    "大宝": 701, "慶雲": 704, "和銅": 708, "霊亀": 715, "養老": 717, "神亀": 724, "天平": 729,
    "天平感宝": 749, "天平勝宝": 749, "天平宝字": 757, "天平神護": 765, "神護景雲": 767, "宝亀": 770,
    "天応": 781, "延暦": 782, "大同": 806, "弘仁": 810, "天長": 824, "承和": 834, "嘉祥": 848, "仁寿": 851,
    "斉衡": 854, "天安": 857, "貞観": 859, "元慶": 877, "仁和": 885, "寛平": 889, "昌泰": 898, "延喜": 901,
    "延長": 923, "承平": 931, "天慶": 938, "天暦": 947, "天徳": 957, "応和": 961, "康保": 964, "安和": 968,
    "天禄": 970, "天延": 973, "貞元": 976, "天元": 978, "永観": 983, "寛和": 985, "永延": 987, "永祚": 989,
    "正暦": 990, "長徳": 995, "長保": 999, "寛弘": 1004, "長和": 1012, "寛仁": 1017, "治安": 1021,
    "万寿": 1024, "長元": 1028, "長暦": 1037, "長久": 1040, "寛徳": 1044, "永承": 1046, "天喜": 1053,
    "康平": 1058, "治暦": 1065, "延久": 1069, "承保": 1074, "承暦": 1077, "永保": 1081, "応徳": 1084,
    "寛治": 1087, "嘉保": 1094, "永長": 1096, "承徳": 1097, "康和": 1099, "長治": 1104, "嘉承": 1106,
    "天仁": 1108, "天永": 1110, "永久": 1113, "元永": 1118, "保安": 1120, "天治": 1124, "大治": 1126,
    "天承": 1131, "長承": 1132, "保延": 1135, "永治": 1141, "康治": 1142, "天養": 1144, "久安": 1145,
    "仁平": 1151, "久寿": 1154, "保元": 1156, "平治": 1159, "永暦": 1160, "応保": 1161, "長寛": 1163,
    "永万": 1165, "仁安": 1166, "嘉応": 1169, "承安": 1171, "安元": 1175, "治承": 1177, "養和": 1181,
    "寿永": 1182, "元暦": 1184, "文治": 1185, "建久": 1190, "正治": 1199, "建仁": 1201, "元久": 1204,
    "建永": 1206, "承元": 1207, "建暦": 1211, "建保": 1213, "承久": 1219, "貞応": 1222, "元仁": 1224,
    "嘉禄": 1225, "安貞": 1227, "寛喜": 1229, "貞永": 1232, "天福": 1233, "文暦": 1234, "嘉禎": 1235,
    "暦仁": 1238, "延応": 1239, "仁治": 1240, "寛元": 1243, "宝治": 1247, "建長": 1249, "康元": 1256,
    "正嘉": 1257, "正元": 1259, "文応": 1260, "弘長": 1261, "文永": 1264, "建治": 1275, "弘安": 1278,
    "正応": 1288, "永仁": 1293, "正安": 1299, "乾元": 1302, "嘉元": 1303, "徳治": 1306, "延慶": 1308,
    "応長": 1311, "正和": 1312, "文保": 1317, "元応": 1319, "元亨": 1321, "正中": 1324, "嘉暦": 1326,
    "元徳": 1329, "元弘": 1331, "建武": 1334, "延元": 1336, "暦応": 1338, "興国": 1340, "康永": 1342,
    "貞和": 1345, "正平": 1346, "観応": 1350, "文和": 1352, "延文": 1356, "康安": 1361, "貞治": 1362,
    "応安": 1368, "建徳": 1370, "文中": 1372, "永和": 1375, "天授": 1375, "康暦": 1379, "永徳": 1381,
    "弘和": 1381, "至徳": 1384, "元中": 1384, "嘉慶": 1387, "康応": 1389, "明徳": 1390, "応永": 1394,
    "正長": 1428, "永享": 1429, "嘉吉": 1441, "文安": 1444, "宝徳": 1449, "享徳": 1452, "康正": 1455,
    "長禄": 1457, "寛正": 1460, "文正": 1466, "応仁": 1467, "文明": 1469, "長享": 1487, "延徳": 1489,
    "明応": 1492, "文亀": 1501, "永正": 1504, "大永": 1521, "享禄": 1528, "天文": 1532, "弘治": 1555,
    "永禄": 1558, "元亀": 1570, "天正": 1573, "文禄": 1592, "慶長": 1596, "元和": 1615, "寛永": 1624,
    "正保": 1644, "慶安": 1648, "承応": 1652, "明暦": 1655, "万治": 1658, "寛文": 1661, "延宝": 1673,
    "天和": 1681, "貞享": 1684, "元禄": 1688, "宝永": 1704, "正徳": 1711, "享保": 1716, "元文": 1736,
    "寛保": 1741, "延享": 1744, "寛延": 1748, "宝暦": 1751, "明和": 1764, "安永": 1772, "天明": 1781,
    "寛政": 1789, "享和": 1801, "文化": 1804, "文政": 1818, "天保": 1830, "弘化": 1844, "嘉永": 1848,
    "安政": 1854, "万延": 1860, "文久": 1861, "元治": 1864, "慶応": 1865, "明治": 1868, "大正": 1912,
    "昭和": 1926, "平成": 1989, "令和": 2019,
}
_ERA_RE = re.compile("(" + "|".join(sorted(ERAS, key=len, reverse=True)) + r")\s*(元|[0-9０-９一二三四五六七八九十〇]+)?\s*年?")

PERIOD_WORDS = {
    "奈良時代": ("nara", 710, 794), "平安時代": ("heian", 794, 1185), "鎌倉時代": ("kamakura", 1185, 1333),
    "南北朝時代": ("nanbokucho", 1336, 1392), "室町時代": ("muromachi", 1336, 1573),
    "戦国時代": ("sengoku", 1467, 1590), "安土桃山時代": ("azuchi_momoyama", 1573, 1603),
    "江戸時代": ("edo", 1603, 1868), "明治時代": ("meiji", 1868, 1912),
    "江戸前期": ("edo", 1603, 1700), "江戸中期": ("edo", 1680, 1780), "江戸後期": ("edo", 1760, 1868),
    "江戸末期": ("edo", 1830, 1868), "幕末": ("edo", 1853, 1868), "室町末期": ("muromachi", 1500, 1573),
    "室町後期": ("muromachi", 1467, 1573), "鎌倉末期": ("kamakura", 1300, 1333), "平安末期": ("heian", 1100, 1185),
    "heian": ("heian", 794, 1185), "kamakura": ("kamakura", 1185, 1333), "muromachi": ("muromachi", 1336, 1573),
    "sengoku": ("sengoku", 1467, 1590), "momoyama": ("azuchi_momoyama", 1573, 1603), "edo": ("edo", 1603, 1868),
}

_KANJI_DIGITS = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def kanji_number(text):
    t = nfkc(text)
    if t.isdigit():
        return int(t)
    if t == "元":
        return 1
    total, current = 0, 0
    for ch in t:
        if ch in _KANJI_DIGITS:
            current = current * 10 + _KANJI_DIGITS[ch] if current else _KANJI_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        else:
            return None
    return total + current


_CENTURY_FR = re.compile(r"\b([XVI]{1,6})e\s+si[eè]cle", re.I)
_CENTURY_JA = re.compile(r"([0-9０-９]{1,2}|[一二三四五六七八九十]+)\s*世紀")
_YEAR_RE = re.compile(r"(?<![0-9])([5-9][0-9]{2}|1[0-9]{3}|20[0-9]{2})(?![0-9])")
_ROMAN = {"I": 1, "V": 5, "X": 10}


def _roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = _ROMAN.get(ch, 0)
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def parse_historical_date(text):
    """Analyse prudente d'une date historique.

    Retourne un dict {start, end, precision, method, period} ou None.
    Ne remplace jamais le texte source : le résultat est une normalisation tracée.
    """
    if not text:
        return None
    t = nfkc(str(text)).strip()
    estimated = any(w in t.lower() for w in ("頃", "ごろ", "?", "？", "vers ", "circa", "ca.", "推定"))

    eras = list(_ERA_RE.finditer(t))
    if eras:
        years = []
        for m in eras:
            base = ERAS[m.group(1)]
            n = kanji_number(m.group(2)) if m.group(2) else None
            years.append(base + n - 1 if n else base)
        exact = all(m.group(2) for m in eras)
        start, end = min(years), max(years)
        precision = "estimated" if estimated else ("year" if exact and start == end else "interval")
        if not exact and len(eras) == 1:
            # ère sans année : intervalle jusqu'au début de l'ère suivante (approximation)
            later = sorted(v for v in ERAS.values() if v > start)
            end = (later[0] - 1) if later else start
            precision = "estimated" if estimated else "interval"
        return {"start": start, "end": end, "precision": precision, "method": "ère japonaise (元号)"}

    years = [int(y) for y in _YEAR_RE.findall(t)]
    if years:
        start, end = min(years), max(years)
        precision = "estimated" if estimated else ("year" if start == end else "interval")
        return {"start": start, "end": end, "precision": precision, "method": "année grégorienne"}

    m = _CENTURY_FR.search(t)
    if m:
        c = _roman_to_int(m.group(1))
        return {"start": (c - 1) * 100 + 1, "end": c * 100, "precision": "century", "method": "siècle"}
    m = _CENTURY_JA.search(t)
    if m:
        c = kanji_number(m.group(1))
        if c:
            return {"start": (c - 1) * 100 + 1, "end": c * 100, "precision": "century", "method": "世紀"}

    low = t.lower()
    for word, (period, start, end) in PERIOD_WORDS.items():
        if word in t or word in low:
            return {"start": start, "end": end, "precision": "period", "method": "période", "period": period}
    return None


def period_for_years(start, end=None):
    """Période historique principale correspondant à une année (règle simple, documentée)."""
    if start is None:
        return ""
    year = start if end is None else (start + end) // 2
    order = [("nara", 710, 793), ("heian", 794, 1184), ("kamakura", 1185, 1332), ("nanbokucho", 1333, 1391),
             ("muromachi", 1392, 1466), ("sengoku", 1467, 1572), ("azuchi_momoyama", 1573, 1602),
             ("edo", 1603, 1867), ("meiji", 1868, 2100)]
    for code, a, b in order:
        if a <= year <= b:
            return code
    return ""
