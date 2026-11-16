"""Cohérence des références : les appels dans le texte et la bibliographie se répondent-ils ?

Vérifications, quelle que soit la norme (voir formes_citation.py) :
  - un appel auteur-date (Dupont, 2020) ou auteur-page (Dupont 12) doit avoir son entrée en bibliographie ;
    même auteur mais autre année : signalé comme approximatif ;
  - un appel numérique [3] ou (3) doit renvoyer à une entrée existante d'une bibliographie numérotée ;
  - un appel de note ¹ doit avoir sa note de bas de page (« 1. Dupont, … ») ou son entrée ;
  - un renvoi (ibid.) doit suivre un autre appel ;
  - une entrée de bibliographie doit être appelée quelque part (sinon : entrée décorative) ;
  - des appels sans aucune bibliographie sont signalés.
"""
import re

from formes_citation import ANNEE, NOM, _normaliser_nom, appels, debut_bibliographie

# « [3] Dupont, A. (2020). … »  « 3. Dupont A. … 2020 »  « Dupont, A. (2020). … »  « DUPONT Alain, 2020, … »
# Une entrée commence par un nom d'auteur suivi d'initiales ou d'un prénom : « Dupont, A. (2020). … »,
# « [3] Dupont, A. … », « 3. Dupont A. … 2020 », « Dupont, Alain. … 2020 », « DUPONT Alain, 2020, … »
INITIALES = r"[A-ZÀ-Ý]\.(?:\s*-?[A-ZÀ-Ý]\.)*"
INITIALES_SANS_POINT = r"[A-ZÀ-Ý]{1,3}(?=[\s,.])"                      # Vancouver : « Zhou B, Khosla A, … »
PRENOM = r"[A-ZÀ-Ý][a-zà-ÿ'’\-]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ'’\-]+)*"
ENTREE = re.compile(
    rf"(?:\[(\d{{1,3}})\]\s*|(?<![\w.])(\d{{1,3}})[.)]\s+)?"           # numéro éventuel
    rf"(?:{INITIALES}\s+)?"                                              # initiales avant le nom (IEEE : C. Lemaire)
    rf"({NOM})(?:\s*,\s*(?:{INITIALES}|{PRENOM})|\s+{INITIALES}|\s+{INITIALES_SANS_POINT}|\s+{PRENOM}\s*,|\s*,)"   # Nom + initiales ou prénom
    rf"[^\n]{{0,300}}?\(?({ANNEE})\)?")                                   # … jusqu'à l'année (Vancouver et IEEE la mettent à la fin)
NOTE_LIGNE = re.compile(rf"(?m)^\s*(\d{{1,2}}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)[.)]?\s+({NOM})")
EXPOSANTS = str.maketrans("¹²³⁴⁵⁶⁷⁸⁹⁰", "1234567890")


def _bibliographie(texte):
    """(début, fin) du titre de la section Bibliographie, ou None."""
    return debut_bibliographie(texte)


def entrees_de_bibliographie(texte):
    """Liste de dicts {numero, auteur, annee, texte} après le titre « Bibliographie / Références », ou None."""
    pos = _bibliographie(texte)
    if pos is None:
        return None
    entrees = []
    for m in ENTREE.finditer(texte[pos[1]:]):
        numero = int(m.group(1) or m.group(2)) if (m.group(1) or m.group(2)) else None
        entrees.append({"numero": numero, "auteur": _normaliser_nom(m.group(3)), "annee": m.group(4),
                        "texte": re.sub(r"\s+", " ", m.group(0)).strip()})
    return entrees


def notes_de_bas_de_page(texte, limite):
    """Notes « 1. Dupont, … » situées avant la bibliographie : {numero, auteur}."""
    notes = []
    for m in NOTE_LIGNE.finditer(texte[:limite]):
        notes.append({"numero": int(m.group(1).translate(EXPOSANTS)), "auteur": _normaliser_nom(m.group(2))})
    return notes


def coherence_references(texte):
    """Retourne {appels, entrees, notes, fantomes, approximatifs, jamais_citees, remarques, bibliographie, numerotee}."""
    pos = _bibliographie(texte)
    corps = texte[:pos[0]] if pos else texte
    entrees = entrees_de_bibliographie(texte)
    numerotee = bool(entrees) and all(e["numero"] is not None for e in entrees)
    liste_appels = appels(corps, numerotee=numerotee)
    notes = notes_de_bas_de_page(texte, len(corps))
    remarques, fantomes, approximatifs = [], [], []

    if entrees is None:
        if liste_appels:
            remarques.append(f"{len(liste_appels)} appel(s) de référence dans le texte, mais aucune section « Bibliographie » ou « Références » : le lecteur ne peut retrouver aucune source.")
        else:
            remarques.append("Aucun appel de référence et aucune bibliographie : ce texte ne s'appuie sur aucune source déclarée.")
        return {"appels": liste_appels, "entrees": [], "notes": notes, "fantomes": liste_appels, "approximatifs": [],
                "jamais_citees": [], "remarques": remarques, "bibliographie": False, "numerotee": False}

    auteurs_entrees = {e["auteur"] for e in entrees}
    cles_entrees = {(e["auteur"], e["annee"]) for e in entrees}
    numeros_entrees = {e["numero"] for e in entrees if e["numero"] is not None}
    numeros_notes = {n["numero"] for n in notes}
    auteurs_appeles, numeros_appeles = set(), set()

    for i, a in enumerate(liste_appels):
        if a["style"] in ("auteur-date", "auteur-page"):
            for auteur in a["auteurs"]:
                auteurs_appeles.add(auteur)
                if auteur not in auteurs_entrees:
                    fantomes.append(a)
                elif a["style"] == "auteur-date" and not any((auteur, an) in cles_entrees for an in a["annees"]):
                    approximatifs.append(a)
        elif a["style"] in ("numerique", "numerique-parentheses"):
            numeros_appeles.update(a["numeros"])
            cible = numeros_entrees if numerotee else set(range(1, len(entrees) + 1))
            if any(n not in cible for n in a["numeros"]):
                fantomes.append(a)
        elif a["style"] == "note":
            numeros_appeles.update(a["numeros"])
            for note in notes:                       # la note « 1. Dupont, … » cite l'auteur Dupont
                if note["numero"] in a["numeros"]:
                    auteurs_appeles.add(note["auteur"])
            cible = numeros_notes or numeros_entrees or set(range(1, len(entrees) + 1))
            if any(n not in cible for n in a["numeros"]):
                fantomes.append(a)
        elif a["style"] == "renvoi" and i == 0:
            fantomes.append(a)                       # (ibid.) sans rien avant

    if numerotee:
        jamais_citees = [e for e in entrees if e["numero"] not in numeros_appeles]
    else:
        jamais_citees = [e for e in entrees if e["auteur"] not in auteurs_appeles]

    def liste(items, cle="texte"):
        return ", ".join(sorted({x[cle][:60] for x in items}))

    if fantomes:
        remarques.append(f"{len(fantomes)} appel(s) sans entrée correspondante en bibliographie : {liste(fantomes)}.")
    if approximatifs:
        remarques.append(f"{len(approximatifs)} appel(s) dont l'année ne correspond pas à l'entrée du même auteur : {liste(approximatifs)}.")
    if jamais_citees:
        remarques.append(f"{len(jamais_citees)} entrée(s) de bibliographie jamais citée(s) dans le texte : {liste(jamais_citees)}.")
    if not remarques:
        remarques.append(f"{len(liste_appels)} appel(s) et {len(entrees)} entrée(s) : tout se correspond.")
    styles = sorted({a["style"] for a in liste_appels})
    if len({s for s in styles if s in ("auteur-date", "auteur-page", "numerique", "numerique-parentheses", "note")}) > 1:
        remarques.append(f"Plusieurs normes mélangées dans le même texte ({', '.join(styles)}) : il faut en choisir une.")
    return {"appels": liste_appels, "entrees": entrees, "notes": notes, "fantomes": fantomes, "approximatifs": approximatifs,
            "jamais_citees": jamais_citees, "remarques": remarques, "bibliographie": True, "numerotee": numerotee}
