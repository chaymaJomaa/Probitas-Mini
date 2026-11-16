"""Indice de style « texte généré par une IA » : un indicateur, jamais une preuve.

Aucun détecteur de texte généré n'est fiable : OpenAI a retiré le sien en 2023 (trop d'erreurs), et
Liang et al. (2023) ont montré que ces outils accusent à tort les personnes qui n'écrivent pas dans
leur langue maternelle. On ne cherche donc pas à « détecter l'IA » : on mesure sept traits de style
visibles et vérifiables, on les affiche un par un, et on les combine en un indice de 0 à 100 qui
sert à ouvrir une discussion, pas à la clore.

Chaque mesure donne un score entre 0 (plutôt humain) et 1 (plutôt généré), interpolé entre une
valeur typiquement humaine et une valeur typiquement générée, puis pondéré.
"""
import re
import statistics

from detecteur import decouper_mots, decouper_paragraphes, decouper_phrases, mots_de_la_phrase, normaliser

TOURNURES = ["il est important de noter", "il convient de noter", "il est essentiel de", "il est crucial de",
             "joue un role crucial", "joue un role essentiel", "joue un role cle", "en outre", "de plus,", "par ailleurs",
             "en conclusion", "en somme", "en resume", "dans l'ensemble", "en definitive", "il est a noter", "notons que",
             "met en lumiere", "souligne l'importance", "dans le paysage", "un large eventail", "une multitude de",
             "favoriser", "optimiser", "s'inscrit dans", "dans un monde en constante evolution", "a l'ere du numerique",
             "constitue un enjeu majeur", "represente un defi", "de maniere significative", "force est de constater",
             "en fin de compte", "pour conclure", "ainsi,", "en effet,", "de ce fait", "dans cette optique", "a cet egard",
             "it is important to note", "it is worth noting", "plays a crucial role", "furthermore", "moreover",
             "additionally", "in conclusion", "in summary", "delve", "tapestry", "landscape", "underscores", "a testament to",
             "comprehensive", "robust", "leverage", "foster", "ever-evolving", "paramount", "multifaceted", "pivotal"]
CONNECTEURS = ["en outre", "de plus", "par ailleurs", "cependant", "toutefois", "ainsi", "enfin", "neanmoins", "en effet",
               "d'une part", "d'autre part", "en conclusion", "en somme", "premierement", "deuxiemement", "troisiemement",
               "finalement", "en resume", "de ce fait", "par consequent", "egalement", "dans ce contexte", "il est important",
               "il convient", "il est essentiel", "il est crucial", "notamment", "furthermore", "moreover", "additionally",
               "however", "overall", "in conclusion", "firstly", "secondly", "finally", "ultimately", "therefore", "thus"]
MARQUES_PERSONNELLES = ["je ", "j'", "a mon avis", "selon moi", "je pense", "je crois", "on a ", "on voit", "bref", "du coup",
                        "franchement", "en fait", "je trouve", "mon ", "ma ", "mes ", "quand meme", "vraiment",
                        "i think", "i believe", "in my opinion", "my ", "i've", "i'm", "honestly", "actually", "basically"]

AVERTISSEMENT = ("Cet indice est un indicateur stylométrique, pas une preuve. Un texte humain très formel, ou écrit dans une "
                 "langue étrangère, obtient souvent un indice élevé ; un texte généré puis retravaillé passe sous le seuil. "
                 "Il ne doit jamais fonder seul une accusation : demandez les brouillons, les sources, une explication orale.")


def _rampe(valeur, humain, ia):
    """0 à la valeur « humaine », 1 à la valeur « générée », linéaire entre les deux, borné."""
    if humain == ia:
        return 0.0
    return max(0.0, min(1.0, (valeur - humain) / (ia - humain)))


def _mattr(mots, fenetre=50):
    """Richesse lexicale indépendante de la longueur : mots distincts / mots, moyenne sur des fenêtres glissantes."""
    if len(mots) <= fenetre:
        return len(set(mots)) / len(mots) if mots else 0.0
    return statistics.fmean(len(set(mots[i:i + fenetre])) / fenetre for i in range(0, len(mots) - fenetre + 1, fenetre // 2))


def indice_ia(texte):
    """Retourne {indice, niveau, fiabilite, mesures: [...], avertissement}."""
    mots = [m[0] for m in decouper_mots(texte) if not m[0].isdigit()]
    phrases = [(d, f) for d, f in decouper_phrases(texte) if len(mots_de_la_phrase(decouper_mots(texte), d, f)) >= 3]
    if len(mots) < 80 or len(phrases) < 3:
        return {"indice": None, "niveau": "non calculé", "mesures": [], "avertissement": AVERTISSEMENT,
                "fiabilite": "Texte trop court (moins de 80 mots ou de 3 phrases) : indice non calculé."}
    tous_mots = decouper_mots(texte)
    texte_norm = normaliser(texte)
    longueurs = [len(mots_de_la_phrase(tous_mots, d, f)) for d, f in phrases]
    mesures = []

    moyenne = statistics.fmean(longueurs)
    cv = statistics.pstdev(longueurs) / moyenne
    mesures.append({"nom": "Variabilité des longueurs de phrases", "valeur": f"CV = {cv:.2f} (moyenne {moyenne:.1f} mots)",
                    "score": _rampe(cv, 0.62, 0.30), "poids": 2.0,
                    "lecture": "L'écriture humaine alterne phrases courtes et longues ; un modèle produit des phrases de taille régulière."})

    richesse = _mattr(mots)
    mesures.append({"nom": "Richesse lexicale (MATTR)", "valeur": f"{richesse:.2f}", "score": _rampe(richesse, 0.80, 0.66), "poids": 0.8,
                    "lecture": "Mots distincts sur mots, par fenêtres de 50. Les textes générés longs répètent leur vocabulaire. Indice faible : l'écrit académique humain est répétitif aussi."})

    occurrences = sum(texte_norm.count(t) for t in TOURNURES)
    exemples = [t for t in TOURNURES if t in texte_norm][:4]
    densite = occurrences / len(phrases) * 100
    mesures.append({"nom": "Tournures typiques des assistants", "valeur": f"{occurrences} occurrence(s), {densite:.0f} pour 100 phrases"
                    + (f" : {', '.join(exemples)}" if exemples else ""), "score": _rampe(densite, 4.0, 28.0), "poids": 2.0,
                    "lecture": "« Il est important de noter », « en outre », « joue un rôle crucial »… formules très fréquentes dans les sorties de modèles."})

    debuts = sum(1 for d, f in phrases if any(normaliser(texte[d:d + 40]).startswith(c) for c in CONNECTEURS))
    mesures.append({"nom": "Phrases ouvertes par un connecteur", "valeur": f"{debuts}/{len(phrases)} ({debuts / len(phrases):.0%})",
                    "score": _rampe(debuts / len(phrases), 0.10, 0.40), "poids": 1.5,
                    "lecture": "« En outre, … », « Ainsi, … », « Cependant, … » en tête de phrase : les modèles enchaînent les connecteurs."})

    paragraphes = decouper_paragraphes(texte)
    tailles = [sum(1 for d, f in phrases if pd <= d < pf) for pd, pf in paragraphes]
    tailles = [t for t in tailles if t]
    if len(tailles) >= 3:
        pm = statistics.fmean(tailles)
        pcv = statistics.pstdev(tailles) / pm
        mesures.append({"nom": "Régularité des paragraphes", "valeur": f"{len(tailles)} paragraphes, CV = {pcv:.2f}",
                        "score": _rampe(pcv, 0.60, 0.20), "poids": 1.0,
                        "lecture": "Des paragraphes de taille presque identique (3 à 5 phrases chacun) sont caractéristiques des textes générés."})

    personnelles = sum(texte_norm.count(m) for m in MARQUES_PERSONNELLES)
    expressives = sum(1 for d, f in phrases if re.search(r"[!?]|\(.*\)|…|\.\.\.", texte[d:f]))
    ratio = (personnelles + expressives) / len(phrases)
    mesures.append({"nom": "Marques personnelles et informelles", "valeur": f"{personnelles} marque(s) personnelle(s), {expressives} phrase(s) avec ?, !, …, parenthèses",
                    "score": 1.0 - _rampe(ratio, 0.0, 0.25), "poids": 1.2,
                    "lecture": "Première personne, avis, questions, exclamations, parenthèses : fréquents chez les humains, rares dans les textes générés."})

    triades = sum(1 for d, f in phrases if re.search(r"\w+,\s+\w+\s+(et|and)\s+\w+", normaliser(texte[d:f])))
    mesures.append({"nom": "Énumérations ternaires (« X, Y et Z »)", "valeur": f"{triades}/{len(phrases)} phrases",
                    "score": _rampe(triades / len(phrases), 0.08, 0.30), "poids": 0.8,
                    "lecture": "Les modèles de langue affectionnent les listes de trois éléments bien équilibrées."})

    total = sum(m["poids"] for m in mesures)
    indice = round(100 * sum(m["score"] * m["poids"] for m in mesures) / total)
    for m in mesures:
        m["score"] = round(m["score"], 2)
        m["tendance"] = "plutôt humain" if m["score"] < 0.34 else ("indécis" if m["score"] < 0.67 else "plutôt généré")
    niveau = "faible" if indice < 35 else ("modéré" if indice < 65 else "élevé")
    fiabilite = ("Texte très court (moins de 150 mots ou de 5 phrases) : l'indice n'est qu'une indication grossière." if len(mots) < 150 or len(phrases) < 5 else
                 "Texte court (moins de 300 mots) : fiabilité très faible." if len(mots) < 300 else
                 "Texte de longueur moyenne : fiabilité limitée." if len(mots) < 800 else
                 "Texte long : les mesures sont plus stables, mais l'indice reste indicatif.")
    return {"indice": indice, "niveau": niveau, "fiabilite": fiabilite, "mesures": mesures, "avertissement": AVERTISSEMENT}
