"""Probitas mini : la page web. Une seule route, une seule page.

    python app.py   puis ouvrir http://127.0.0.1:5000

Le moteur est dans detecteur.py ; ce fichier reçoit le texte, appelle analyser(), puis prépare
ce que la page affiche : texte surligné, verdict, barre de répartition, explications.
"""
import html
import threading
import webbrowser
from pathlib import Path

from flask import Flask, render_template, request

from detecteur import GRAVITE, _index_source, analyser, charger_corpus, lire_fichier, nettoyer
from references import coherence_references
from style_ia import indice_ia

app = Flask(__name__)
DOSSIER_CORPUS = Path(__file__).parent / "corpus"
_corpus = {"cle": None, "sources": []}


def corpus_actuel():
    """Les sources, relues seulement si un fichier du dossier corpus/ a changé (lire 4 PDF prend 2 s)."""
    cle = tuple(sorted((p.name, p.stat().st_mtime) for p in DOSSIER_CORPUS.rglob("*") if p.is_file()))
    if cle != _corpus["cle"]:
        _corpus.update(cle=cle, sources=charger_corpus(DOSSIER_CORPUS))
        for nom, texte, commun in _corpus["sources"]:
            _index_source(texte)                       # empreintes calculées une fois pour toutes
    return _corpus["sources"]

COULEURS = {  # catégorie -> classe CSS (voir templates/page.html)
    "copie non citée": "rose",
    "référence qui ne désigne pas la source": "jaune",
    "copie référencée sans guillemets": "jaune",
    "guillemets sans référence": "jaune",
    "copie retouchée": "jaune",
    "reformulation citée": "vert",
    "citation correcte": "vert",
    "texte commun autorisé": "gris",
    "zone ignorée": "gris",
}

EXPLICATIONS = {  # catégorie -> (ce que c'est, quoi faire)
    "copie non citée": ("Texte repris mot pour mot, sans guillemets ni référence à la source.",
                        "Mettez le passage entre guillemets et ajoutez la référence (auteur, année), ou reformulez avec vos mots en citant la source."),
    "référence qui ne désigne pas la source": ("Une référence accompagne le passage, mais elle n'indique ni l'auteur ni l'année du texte d'où il vient.",
                                               "Vérifiez la référence : elle doit désigner la source réellement utilisée."),
    "copie référencée sans guillemets": ("La source est référencée, mais le texte est repris mot pour mot sans guillemets : le lecteur croit lire vos mots.",
                                         "Ajoutez des guillemets autour du passage repris."),
    "guillemets sans référence": ("Le passage est entre guillemets mais aucune référence n'indique d'où il vient.",
                                  "Ajoutez l'appel de référence juste après la citation."),
    "copie retouchée": ("Phrase presque identique à une phrase de la source, avec quelques mots changés, sans référence.",
                        "Changer quelques mots ne suffit pas : citez la source, ou reformulez vraiment avec vos mots en la citant."),
    "reformulation citée": ("Idée reprise avec vos mots, ou quelques mots repris, dans un paragraphe qui cite sa source : pratique correcte.",
                            "Rien à faire."),
    "citation correcte": ("Passage entre guillemets avec sa référence : citation légitime, exclue du taux de plagiat.",
                          "Rien à faire. Vérifiez seulement que la citation reste courte et utile."),
    "texte commun autorisé": ("Texte que tout le monde a le droit de reprendre (énoncé, consignes) : ni similarité ni plagiat.", "Rien à faire."),
    "zone ignorée": ("Titre ou bibliographie : ce n'est pas du texte rédigé, il n'est pas jugé.", "Rien à faire."),
}

METHODES = {"mots identiques": "Suite de mots identiques retrouvée dans la source (empreintes de 5 mots, trous d'un ou deux mots tolérés).",
            "vocabulaire": "Phrase dont le vocabulaire est presque celui d'une phrase de la source (TF-IDF, cosinus).",
            "ressemblance des lettres": "Phrase retrouvée par comparaison des lettres : le texte de la source est abîmé par l'extraction PDF."}


def verdict(resultat):
    """Une phrase, et un niveau pour la couleur : ok / attention / alerte / critique.
    Le niveau suit le taux de plagiat potentiel ; la phrase distingue les reprises sans aucune citation (rose)
    des reprises dont la citation est incorrecte ou incomplète (jaune : à vérifier avec l'auteur)."""
    taux = resultat["plagiat_potentiel"]
    rose = resultat["par_categorie"].get("copie non citée", 0) / resultat["n_mots"]
    if taux < 0.03:
        return "Aucun signe notable de reprise non citée. À confirmer par une lecture humaine.", "ok"
    if taux < 0.12:
        return "Quelques passages à vérifier : probablement des maladresses de citation.", "attention"
    if rose < 0.03:
        return "Passages repris avec une citation incorrecte ou incomplète : à reprendre avec l'auteur.", "alerte"
    if taux < 0.30:
        return "Similarités importantes avec des sources non citées : examen approfondi nécessaire.", "alerte"
    return "Reprise massive de sources non citées : entretien avec l'auteur indispensable.", "critique"


def preparer_passages(texte, resultat):
    """Numérote les passages, leur attache une explication et une méthode lisible, et attribue à chaque
    mot du texte le passage le plus grave qui le couvre (pour relier le surlignage au panneau de détail)."""
    passages = []
    for n, p in enumerate(resultat["passages"], start=1):
        cle = "mots identiques" if "identiques" in p["methode"] else ("vocabulaire" if "vocabulaire" in p["methode"] else "ressemblance des lettres")
        passages.append({**p, "id": n, "couleur": COULEURS[p["categorie"]], "texte": texte[p["debut"]:p["fin"]],
                         "explication": EXPLICATIONS[p["categorie"]][0], "conseil": EXPLICATIONS[p["categorie"]][1],
                         "methode_detail": METHODES[cle]})
    gravite = lambda p: GRAVITE.get(p["categorie"], 3)
    passage_du_mot = [None] * len(resultat["mots"])
    for p in sorted(passages, key=gravite):
        for i, (_, debut, _) in enumerate(resultat["mots"]):
            if p["debut"] <= debut < p["fin"] and passage_du_mot[i] is None \
                    and resultat["etiquettes"][i] and resultat["etiquettes"][i][0] == p["categorie"]:
                passage_du_mot[i] = p["id"]
    return passages, passage_du_mot


def surligner(texte, resultat, passage_du_mot):
    """Reconstruit le texte en HTML : chaque suite de mots qui porte la même étiquette (catégorie,
    source, passage) est entourée d'une balise <mark> colorée, reliée au panneau de détail."""
    morceaux, position, courante = [], 0, None
    for (mot, debut, fin), etiquette, pid in zip(resultat["mots"], resultat["etiquettes"], passage_du_mot):
        cle = (etiquette, pid)
        if cle != courante:
            if courante and courante[0] is not None:
                morceaux.append("</mark>")
            morceaux.append(html.escape(texte[position:debut]))
            if etiquette is not None:
                cat, source = etiquette
                attrs = f' data-passage="{pid}"' if pid else ""
                morceaux.append(f'<mark class="{COULEURS[cat]}"{attrs} tabindex="0" title="{html.escape(cat)}">')
            courante = cle
        else:
            morceaux.append(html.escape(texte[position:debut]))
        morceaux.append(html.escape(texte[debut:fin]))
        position = fin
    if courante and courante[0] is not None:
        morceaux.append("</mark>")
    morceaux.append(html.escape(texte[position:]))
    return "".join(morceaux)


def repartition(resultat):
    """Mots par couleur, pour la barre et la légende."""
    cats = resultat["par_categorie"]
    parts = {"rose": 0, "jaune": 0, "vert": 0, "gris": 0}
    for cat, n in cats.items():
        parts[COULEURS.get(cat, "gris")] += n
    return parts


@app.route("/", methods=["GET", "POST"])
def accueil():
    sources = corpus_actuel()
    if request.method == "GET":
        return render_template("page.html", resultat=None, sources=sources)
    fichier = request.files.get("fichier")
    if fichier and fichier.filename:
        try:
            texte, nom = lire_fichier(fichier.filename, fichier.read()), fichier.filename
        except Exception as erreur:
            return render_template("page.html", resultat=None, sources=sources, erreur=str(erreur))
    else:
        texte, nom = nettoyer(request.form.get("texte", "")), "Texte collé"
    if not texte:
        return render_template("page.html", resultat=None, sources=sources, erreur="Déposez un fichier (txt, pdf, docx) ou collez un texte.")
    resultat = analyser(texte, sources, nom)
    passages, passage_du_mot = preparer_passages(texte, resultat)
    phrase, niveau = verdict(resultat)
    return render_template("page.html", resultat=resultat, nom=nom, sources=sources, texte=texte,
                           texte_surligne=surligner(texte, resultat, passage_du_mot), passages=passages,
                           parts=repartition(resultat), verdict=phrase, niveau=niveau, couleurs=COULEURS,
                           ia=indice_ia(texte), refs=coherence_references(texte))


if __name__ == "__main__":
    print(f"Lecture du corpus : {len(corpus_actuel())} source(s).")
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
