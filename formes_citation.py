"""Toutes les formes d'appel de référence reconnues, pour toutes les normes courantes.

| Norme                         | Exemples d'appel dans le texte                                   | style        |
| APA, Harvard, Chicago, ISO 690 | (Lemaire, 2024, p. 12) (Lemaire 2024: 12) (LEMAIRE, 2024) [Lemaire, 2024] | auteur-date  |
|                               | Lemaire (2024) · Lemaire et Martin (2019, p. 4) · (Lemaire et al., 2021) |              |
|                               | (Lemaire, 2020, 2024 ; Whitfield, 2023)                           |              |
| MLA (auteur-page, sans année)  | (Lemaire 12) · (Lemaire et Martin 45-46)                          | auteur-page  |
| Vancouver, IEEE, ISO numérique | [3] · [3, 7] · [3-5] · (3) · (3, 7)                               | numerique    |
| Notes de bas de page           | plagiat¹ · plagiat^1                                              | note         |
| Renvois                        | (ibid.) · (ibid., p. 4) · (op. cit.) · (id.) · (loc. cit.)        | renvoi       |

Un appel est reconnu par sa forme, pas par son sens : « (Figure 3) » n'est pas une référence, d'où
la liste MOTS_EXCLUS. La forme « (3) » n'est comptée comme référence numérique que si le document
a une bibliographie numérotée, sinon elle désigne trop souvent autre chose (une énumération, un calcul).
"""
import re

GUILLEMETS = re.compile(r"«[^»]{3,}»|“[^”]{3,}”|„[^“]{3,}“|\"[^\"]{3,}\"")

ANNEE = r"(?:1[6-9]|20)\d{2}[a-z]?"
NOM = r"(?:(?:de|du|des|van|von|le|la|el|al|da|di)\s+)?[A-ZÀ-Ý][\w'’\-]+"
AUTEURS = rf"{NOM}(?:\s*(?:,|et|and|&)\s*{NOM})*(?:\s*,?\s+et\s+al\.?)?"
PAGES = r"(?:\s*[,:;]?\s*(?:p{1,2}\.?|pages?|§)?\s*\d{1,4}(?:\s*[-–]\s*\d{1,4})?)?"
ANNEES = rf"{ANNEE}(?:\s*,\s*{ANNEE})*"
UN_AUTEUR_DATE = rf"{AUTEURS}\s*,?\s*{ANNEES}{PAGES}"

STYLES = {
    "auteur-date": re.compile(
        rf"[\(\[]\s*(?:voir|cf\.?|see|d['’]après|selon|e\.g\.,?)?\s*{UN_AUTEUR_DATE}(?:\s*;\s*{UN_AUTEUR_DATE})*\s*[\)\]]"
        rf"|{AUTEURS}\s*\(\s*{ANNEES}{PAGES}\s*\)"),
    "auteur-page": re.compile(rf"\(\s*{AUTEURS}\s+\d{{1,4}}(?:\s*[-–]\s*\d{{1,4}})?\s*\)"),
    "numerique": re.compile(r"\[\s*\d{1,3}(?:\s*[,;–\-]\s*\d{1,3})*\s*\]"),
    "numerique-parentheses": re.compile(r"\(\s*\d{1,3}(?:\s*[,;–\-]\s*\d{1,3})*\s*\)"),
    "note": re.compile(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+|\^\d{1,2}\b"),
    "renvoi": re.compile(r"\(\s*(?:ibid|idem|id|op\.\s*cit|loc\.\s*cit)\.?[^()]*\)", re.IGNORECASE),
}
MOTS_EXCLUS = {"figure", "fig", "tableau", "table", "chapitre", "section", "annexe", "partie", "article", "art",
               "voir", "page", "exemple", "question", "etape", "niveau", "groupe", "classe", "version", "note"}
EXPOSANTS = str.maketrans("¹²³⁴⁵⁶⁷⁸⁹⁰", "1234567890")


def _normaliser_nom(nom):
    import unicodedata
    sans = "".join(c for c in unicodedata.normalize("NFKD", nom) if not unicodedata.combining(c))
    return re.sub(r"^(?:de|du|des|van|von|le|la|el|al|da|di)\s+", "", sans.lower()).strip()


def appels(texte, numerotee=False):
    """Liste des appels de référence du texte, chacun un dict :
    {debut, fin, texte, style, auteurs: [noms normalisés], annees: [...], numeros: [...]}.
    `numerotee` : la bibliographie est numérotée, donc « (3) » est un appel numérique."""
    trouves = []
    for style, rx in STYLES.items():
        if style == "numerique-parentheses" and not numerotee:
            continue
        for m in rx.finditer(texte):
            brut = m.group(0)
            auteurs = [_normaliser_nom(a) for a in re.findall(NOM, brut)] if style in ("auteur-date", "auteur-page") else []
            auteurs = [a for a in auteurs if a not in MOTS_EXCLUS and not re.fullmatch(ANNEE, a)]
            if style in ("auteur-date", "auteur-page") and not auteurs:
                continue
            annees = re.findall(rf"\b{ANNEE}\b", brut) if style == "auteur-date" else []
            if style in ("numerique", "numerique-parentheses", "note"):
                nombres = re.findall(r"\d+", brut.translate(EXPOSANTS))
                numeros = []
                for partie in re.split(r"[,;]", brut.translate(EXPOSANTS).strip("[]() ^")):
                    bornes = re.findall(r"\d+", partie)
                    if len(bornes) == 2 and re.search(r"[-–]", partie):
                        numeros.extend(range(int(bornes[0]), int(bornes[1]) + 1))
                    else:
                        numeros.extend(int(b) for b in bornes)
            else:
                numeros = []
            trouves.append({"debut": m.start(), "fin": m.end(), "texte": brut.strip(), "style": style,
                            "auteurs": auteurs, "annees": annees, "numeros": numeros})
    # un même endroit ne compte qu'une fois (Lemaire (2024) contient (2024)…) : on garde le plus long
    trouves.sort(key=lambda a: (a["debut"], -(a["fin"] - a["debut"])))
    resultat = []
    for a in trouves:
        if resultat and a["debut"] < resultat[-1]["fin"]:
            continue
        resultat.append(a)
    return resultat


BIBLIOGRAPHIE = re.compile(r"^\s*(bibliographie|r[ée]f[ée]rences?(?:[ \t]+bibliographiques)?|references|sources|webographie|"
                           r"sitographie|ouvrages[ \t]+cit[ée]s|works[ \t]+cited|liste[ \t]+des[ \t]+r[ée]f[ée]rences)\s*:?\s*$",
                           re.IGNORECASE | re.MULTILINE)
_ENTREE_PROBABLE = re.compile(rf"{NOM}\s*,?\s+(?:[A-ZÀ-Ý]\.|[A-ZÀ-Ý][a-zà-ÿ'’\-]+\s*[,.])|\[\d{{1,3}}\]|\b\d{{1,3}}[.)]\s+[A-ZÀ-Ý]")


def debut_bibliographie(texte):
    """(début, fin) du titre de la section Bibliographie / Références, ou None.
    On prend le dernier titre situé dans la seconde partie du texte, ou, s'il est plus haut, un titre suivi
    d'au moins deux lignes qui ressemblent à des entrées (un devoir court peut avoir une longue bibliographie)."""
    titres = list(BIBLIOGRAPHIE.finditer(texte))
    for m in reversed(titres):
        if m.start() >= len(texte) * 0.3 or len(_ENTREE_PROBABLE.findall(texte[m.end():m.end() + 2000])) >= 2:
            return m.start(), m.end()
    return None


def premier_appel(texte, numerotee=False):
    """Le premier appel de référence trouvé dans un morceau de texte, ou None."""
    a = appels(texte, numerotee)
    return a[0] if a else None
