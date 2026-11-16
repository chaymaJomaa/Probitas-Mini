"""Probitas mini : un détecteur de plagiat lisible en entier, qui ne crie pas « plagiat » trop vite.

Trois idées, dans cet ordre :
  1. découper le texte en mots, phrases et paragraphes (normaliser, decouper_*) et mettre de côté
     ce qui ne doit pas être jugé : titres, bibliographie, notes, énoncé commun (zones_ignorees, corpus/commun) ;
  2. comparer avec chaque source :
       - groupes de K mots identiques        -> copie mot pour mot      (passages_identiques)
       - vocabulaire presque identique       -> copie retouchée         (phrases_retouchees, TF-IDF + cosinus)
       - lettres presque identiques          -> secours si la source est abîmée (passages_approximatifs)
  3. décider si c'est une citation ou une faute (categorie) : guillemets, référence, et vérification que
     la référence désigne bien la source retrouvée (meta_source) ; puis compter (analyser).

Usage en console :  python detecteur.py tests/A01_copie_brute.txt
Les sources sont les fichiers .txt, .pdf et .docx du dossier corpus/ ; ceux de corpus/commun/
(énoncé, consignes) sont du texte que tout le monde a le droit de reprendre.
"""
import math
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

from formes_citation import BIBLIOGRAPHIE, GUILLEMETS, _ENTREE_PROBABLE, appels, debut_bibliographie, premier_appel

K = 5                      # K mots identiques à la suite = passage copié
SEUIL_VOCABULAIRE = 0.75   # cosinus TF-IDF au-dessus duquel une phrase est une « copie retouchée »
MOTS_PLEINS_MIN = 3        # un passage copié doit contenir au moins 3 mots porteurs de sens
CITATION_FORTE = 8         # à partir de 8 mots identiques, la coïncidence est exclue : confiance forte
PART_CITATIONS_MAX = 0.30  # au-delà de 30 % de citations correctes, on le signale (citation abusive ?)

# Mots vides : ils ne comptent pas comme « mots porteurs de sens » dans un passage.
MOTS_VIDES = set("""le la les l un une des du de d au aux et ou mais donc car que qui dont ce cet cette ces
    on il elle ils elles nous vous je tu me te se y en ne pas plus est sont a ont etre avoir dans sur sous
    avec sans pour par entre comme aussi alors ainsi puis encore tout tous toute toutes son sa ses mon ma
    mes notre nos votre vos leur leurs meme autre si the a an and or of to in on at by with from is are was
    were be this that these those it its as for not""".split())

# Formules consacrées : tournures que tout le monde emploie, qui n'appartiennent à personne.
# Un passage qui n'est fait que d'une formule n'est pas un emprunt. (Mots normalisés : sans accents ni majuscules.)
FORMULES = """in this paper we propose | in this paper we | in this work we | to the best of our knowledge |
    the rest of this paper is organized as follows | the remainder of this paper | experimental results demonstrate |
    experimental results show that | extensive experiments show that | state of the art | we propose a novel |
    as shown in figure | as shown in table | it is worth noting that | it is important to note that | on the other hand |
    in other words | for example | for instance | in addition | a wide range of | plays an important role in | future work |
    our main contributions are | in conclusion | in summary | as a result | in this section we |
    dans le cadre de ce travail | dans le cadre de cette etude | au terme de ce travail | dans un premier temps |
    dans un second temps | dans un deuxieme temps | nous proposons dans cet article | dans cet article nous proposons |
    les resultats montrent que | les resultats obtenus montrent que | il est important de noter que |
    il convient de noter que | d une part | d autre part | en d autres termes | c est a dire | par exemple |
    en conclusion | en effet | a notre connaissance | l etat de l art | dans la section suivante |
    comme le montre la figure | comme indique dans le tableau | ce travail s inscrit dans | la suite de cet article"""
FORMULES = [f.strip() for f in FORMULES.split("|") if f.strip()]

# Catégories, de la plus grave (0) à la plus légitime. Seules les gravités 0 et 1 comptent dans le plagiat ;
# la gravité 3 (texte commun autorisé) ne compte même pas dans la similarité.
GRAVITE = {
    "copie non citée": 0,
    "référence qui ne désigne pas la source": 1,
    "copie référencée sans guillemets": 1,
    "guillemets sans référence": 1,
    "copie retouchée": 1,
    "reformulation citée": 2,
    "citation correcte": 2,
    "texte commun autorisé": 3,
}


# ----------------------------------------------------------------------------- 0. lire un fichier
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st", "…": "...",
             " ": " ", " ": " ", " ": " "}          # ligatures de PDF, espaces insécables
FIN_DE_LIGNE = re.compile(r"[.!?»”\"')\]]$")                        # une ligne qui finit ainsi est vraiment finie
DEBUT_D_ENTREE = re.compile(r"\[\d{1,3}\]|\d{1,3}[.)]\s|[•\-–]\s")  # [12] … / 3. … / puces : une nouvelle entrée


def _recoller(paragraphe):
    """À l'intérieur d'un paragraphe, un saut de ligne simple est le plus souvent un retour à la ligne
    de PDF (« la méthode\nproposée ») : il devient un espace. On le garde seulement s'il sépare deux
    choses vraiment distinctes : une ligne finie par une ponctuation, un titre « Bibliographie »,
    une entrée numérotée, une puce."""
    lignes = paragraphe.split("\n")
    sortie = [lignes[0].strip()]
    for ligne in lignes[1:]:
        ligne, avant = ligne.strip(), sortie[-1]
        if (not avant or FIN_DE_LIGNE.search(avant) or BIBLIOGRAPHIE.match(avant) or BIBLIOGRAPHIE.match(ligne)
                or DEBUT_D_ENTREE.match(ligne)):
            sortie.append(ligne)
        else:
            sortie[-1] = avant + " " + ligne
    return "\n".join(sortie)


def nettoyer(texte):
    """Répare les défauts habituels d'un texte extrait d'un PDF ou copié depuis un lecteur PDF :
    ligatures (« ﬁ »), tirets conditionnels, mots coupés en fin de ligne (« détec-\ntion »), espace perdu
    après un point (« annotation.We »), retours à la ligne au milieu des phrases (voir _recoller) ;
    une ligne vide reste un changement de paragraphe."""
    texte = texte.replace("\r\n", "\n").replace("­", "").replace("​", "").replace("﻿", "")
    for a, b in LIGATURES.items():
        texte = texte.replace(a, b)
    texte = re.sub(r"[‐‑‒–−]", "-", texte)     # tirets typographiques -> tiret simple
    texte = re.sub(r"(\w)-\s+(\w)", r"\1\2", texte)                   # recolle « vi- sual » et « vi-\nsual »
    texte = re.sub(r"([a-zà-ÿ]{2,})\.([A-ZÀ-Ý][a-zà-ÿ])", r"\1. \2", texte)   # « annotation.We »
    texte = re.sub(r"[ \t]*\n[ \t]*\n[ \t\n]*", "\n\n", texte)         # ligne vide = paragraphe
    texte = "\n\n".join(_recoller(p) for p in texte.split("\n\n"))
    return re.sub(r"[ \t]{2,}", " ", texte).strip()


def lire_fichier(nom, octets):
    """Texte d'un fichier d'après son extension : .txt (ou .md), .pdf (pypdf), .docx (python-docx).
    Un PDF scanné ne contient que des images : il revient vide, et on le dit."""
    extension = Path(nom).suffix.lower()
    if extension == ".pdf":
        from io import BytesIO
        from pypdf import PdfReader                      # python -m pip install --user pypdf
        texte = "\n\n".join((page.extract_text() or "") for page in PdfReader(BytesIO(octets)).pages)
        if not texte.strip():
            raise ValueError(f"{nom} : ce PDF ne contient pas de texte (document scanné ?).")
        return nettoyer(texte)
    if extension == ".docx":
        from io import BytesIO
        import docx                                      # python -m pip install --user python-docx
        return nettoyer("\n\n".join(p.text for p in docx.Document(BytesIO(octets)).paragraphs))
    if extension in (".txt", ".md", ""):
        for encodage in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return nettoyer(octets.decode(encodage))
            except UnicodeDecodeError:
                continue
    raise ValueError(f"{nom} : format non pris en charge (txt, pdf ou docx).")


# ----------------------------------------------------------------------------- 1. découper
def normaliser(mot):
    """Minuscules, sans accents, sans tiret : « Éthique » et « ethique » deviennent le même mot,
    et « vi-sual » (mot coupé par l'extraction) devient « visual »."""
    sans_accents = "".join(c for c in unicodedata.normalize("NFKD", mot) if not unicodedata.combining(c))
    return sans_accents.lower().replace("-", "")


def decouper_mots(texte):
    """Liste de (mot normalisé, position de début, position de fin). Les positions servent au surlignage.
    Un mot avec un tiret à l'intérieur (« black-box », « vi-sual ») compte pour un seul mot."""
    return [(normaliser(m.group()), m.start(), m.end()) for m in re.finditer(r"[^\W_]+(?:-[^\W_]+)*", texte)]


ABREVIATIONS = set("""al cf etc ex fig figs p pp vol no chap art ed éd eds coll op cit ibid id loc trad env
    m mm mme mlle mgr dr pr prof me mr mrs ms st ste e.g i.e vs n° nos tel tél janv fév févr avr juil sept oct nov déc""".split())


def decouper_phrases(texte):
    """Liste de (début, fin) des phrases : on coupe après . ! ? suivis d'un blanc, ou à la ligne,
    sauf si le point termine une abréviation (« et al. », « p. 12 », « M. Dupont », « C. Lemaire »)."""
    phrases, debut = [], 0
    for m in re.finditer(r"[.!?]+[\"»”)]*\s+|\n+", texte):
        if m.group().startswith("."):
            avant = re.search(r"([\w°]+)\.$", texte[:m.start() + 1])      # le mot juste avant le point
            if avant and (avant.group(1).lower() in ABREVIATIONS or (len(avant.group(1)) == 1 and avant.group(1).isupper())):
                continue
            apres = texte[m.end():m.end() + 1]
            if apres and apres.islower():                                   # « p. 12 » ou abréviation inconnue
                continue
        if m.start() > debut:
            phrases.append((debut, m.start()))
        debut = m.end()
    if debut < len(texte):
        phrases.append((debut, len(texte)))
    return phrases


def decouper_paragraphes(texte):
    """Liste de (début, fin) des paragraphes, séparés par une ligne vide."""
    paragraphes, debut = [], 0
    for m in re.finditer(r"\n\s*\n", texte):
        paragraphes.append((debut, m.start()))
        debut = m.end()
    paragraphes.append((debut, len(texte)))
    return paragraphes


def mots_de_la_phrase(mots, debut, fin):
    """Les mots (déjà découpés) qui tombent entre deux positions."""
    return [m for m in mots if debut <= m[1] < fin]


def mots_par_phrase(mots, phrases):
    """Pour chaque phrase, la liste de ses mots normalisés (un seul parcours : mots et phrases sont triés)."""
    resultat, i = [], 0
    for debut, fin in phrases:
        while i < len(mots) and mots[i][1] < debut:
            i += 1
        j = i
        while j < len(mots) and mots[j][1] < fin:
            j += 1
        resultat.append([m[0] for m in mots[i:j]])
        i = j
    return resultat


NOTE_BIBLIO = re.compile(r"(?m)^\s*(?:\d{1,2}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)[.)]?\s+[A-ZÀ-Ý][^\n]*\b(?:1[6-9]|20)\d{2}\b[^\n]*$")


def zones_ignorees(texte):
    """Zones qu'on ne juge pas : les titres (ligne courte sans ponctuation finale), les notes de bas de
    page qui citent une référence (« 1. Zhang, Z. et al., …, 2025 ») et la bibliographie (tout ce qui suit
    un titre « Bibliographie » ou « Références »)."""
    zones = []
    for m in re.finditer(r"[^\n]+", texte):
        ligne = m.group().strip()
        if ligne and len(ligne.split()) <= 12 and ligne[-1] not in ".!?»\"”":
            zones.append((m.start(), m.end()))
    for m in NOTE_BIBLIO.finditer(texte):
        if _ENTREE_PROBABLE.search(m.group()):
            zones.append((m.start(), m.end()))
    biblio = debut_bibliographie(texte)
    if biblio:
        zones.append((biblio[0], len(texte)))
    return zones


# ----------------------------------------------------------------------------- 2. comparer
@lru_cache(maxsize=32)
def _index_source(texte_src, k=K):
    """Tout ce qu'on calcule une fois par source : ses mots, ses phrases, l'empreinte de chaque groupe de
    K mots (-> positions), et l'empreinte de chaque suite de 5 lettres (-> positions, pour le secours)."""
    mots, phrases = decouper_mots(texte_src), decouper_phrases(texte_src)
    positions = {}
    for i in range(len(mots) - k + 1):
        positions.setdefault(tuple(m[0] for m in mots[i:i + k]), []).append(i)
    lettres = re.sub(r"[^a-z0-9]", "", " ".join(m[0] for m in mots))
    index_lettres = {}
    for i in range(len(lettres) - 4):
        index_lettres.setdefault(lettres[i:i + 5], []).append(i)
    return mots, phrases, positions, lettres, index_lettres, mots_par_phrase(mots, phrases)


def _mots_pleins(mots):
    """Combien de mots porteurs de sens, une fois retirées les formules consacrées ?"""
    texte = " " + " ".join(m[0] for m in mots) + " "
    for formule in FORMULES:
        texte = texte.replace(f" {formule} ", "  ")
    return sum(1 for mot in texte.split() if mot not in MOTS_VIDES and not mot.isdigit())


def passages_identiques(mots_doc, positions_src, analysable, k=K, pont=3):
    """Passages du document dont K mots consécutifs se retrouvent tels quels dans la source.

    Les groupes de K mots de la source sont rangés dans un dictionnaire (une « empreinte » par groupe,
    avec ses positions : `positions_src`) ; on fait glisser une fenêtre de K mots sur le document. Les
    groupes qui se suivent sont fusionnés en un passage. Tolérance aux mots abîmés (extraction PDF, mot
    coupé en fin de ligne, faute de frappe) : deux groupes séparés d'au plus k + 2 mots dans le document,
    et placés au même endroit de la source (décalage égal à `pont` mots près), sont réunis en un seul
    passage, trou compris. Un groupe qui contient un mot « non analysable » (titre, bibliographie, texte
    commun) est sauté, et un passage qui n'a pas assez de mots porteurs de sens, une fois retirées les
    formules consacrées (« dans le cadre de ce travail »), est écarté.
    """
    passages = []                                    # [début doc, fin doc, décalage source − document]
    for i in range(len(mots_doc) - k + 1):
        if not all(analysable[i:i + k]):
            continue
        candidats = positions_src.get(tuple(m[0] for m in mots_doc[i:i + k]))
        if not candidats:
            continue
        if passages and i <= passages[-1][1] + k + 2:
            attendu = passages[-1][2]                # on préfère l'occurrence qui prolonge le passage
            j = min(candidats, key=lambda c: abs((c - i) - attendu))
            if abs((j - i) - attendu) <= pont:
                passages[-1][1], passages[-1][2] = i + k, j - i
                continue
        passages.append([i, i + k, candidats[0] - i])
    return [(d, f) for d, f, _ in passages if _mots_pleins(mots_doc[d:f]) >= MOTS_PLEINS_MIN]


def vecteurs_tfidf(phrases_en_mots):
    """Un vecteur par phrase : poids de chaque mot = fréquence dans la phrase × rareté dans l'ensemble.
    « le » ou « de » sont partout et pèsent presque rien, « disciplines » pèse lourd. Chaque vecteur est
    normalisé (longueur 1) pour que le cosinus soit un simple produit."""
    n = len(phrases_en_mots)
    presence = Counter()
    for phrase in phrases_en_mots:
        presence.update(set(phrase))
    idf = {mot: math.log((1 + n) / (1 + d)) + 1 for mot, d in presence.items()}
    vecteurs = []
    for phrase in phrases_en_mots:
        tf = Counter(phrase)
        v = {mot: tf[mot] * idf[mot] for mot in tf}
        norme = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecteurs.append({mot: x / norme for mot, x in v.items()})
    return vecteurs


def cosinus(a, b):
    """Ressemblance entre deux vecteurs normalisés : 1 = mêmes mots, mêmes poids ; 0 = rien en commun."""
    return sum(poids * b[mot] for mot, poids in a.items() if mot in b)


def phrases_retouchees(mots_doc, phrases_doc, phrases_src_en_mots, seuil=SEUIL_VOCABULAIRE, exclure=frozenset()):
    """Phrases du document dont le vocabulaire est presque celui d'une phrase de la source
    (`phrases_src_en_mots` : la liste des mots de chaque phrase de la source, voir mots_par_phrase).
    Les mots des appels de référence (« (Zhou et al., 2016) ») et les nombres sont laissés de côté : ils
    ne disent rien du style. Retourne des (index de phrase du document, index de phrase de la source, cosinus)."""
    doc = [[m[0] for i, m in enumerate(mots_doc) if d <= m[1] < f and i not in exclure and not m[0].isdigit()] for d, f in phrases_doc]
    src = [[mot for mot in phrase if not mot.isdigit()] for phrase in phrases_src_en_mots]
    vecteurs = vecteurs_tfidf(doc + src)
    v_doc, v_src = vecteurs[:len(doc)], vecteurs[len(doc):]
    resultats = []
    for i, a in enumerate(v_doc):
        if len(doc[i]) < 6:                      # titres et bouts de phrase : trop courts pour juger
            continue
        meilleur = max(((cosinus(a, b), j) for j, b in enumerate(v_src)), default=(0.0, None))
        if meilleur[0] >= seuil:
            resultats.append((i, meilleur[1], round(meilleur[0], 2)))
    return resultats


def grammes_lettres(chaine, n=5):
    """Ensemble des suites de n lettres d'une chaîne sans espaces : « leplagiat » -> {lepla, eplag, plagi, lagia, agiat}."""
    chaine = re.sub(r"[^a-z0-9]", "", normaliser(chaine))
    return {chaine[i:i + n] for i in range(len(chaine) - n + 1)}


def passages_approximatifs(mots_doc, phrases_doc, lettres_src, index_src, analysable, deja, seuil=0.45):
    """Couche de secours quand le texte d'une source est abîmé par l'extraction PDF (mots collés,
    lettres manquantes, colonnes mélangées) : on compare les LETTRES, pas les mots.

    Pour chaque phrase du document, on prend ses suites de 5 lettres (espaces retirés). L'index de la
    source dit où chacune apparaît : les endroits qui reçoivent le plus de « votes » sont les seuls
    candidats, et on y calcule la ressemblance exacte, Jaccard (part commune des suites de lettres).
    Deux textes identiques à 10 % de défauts près gardent un Jaccard > 0,5 ; deux textes différents
    restent sous 0,1. Retourne des (index de phrase, meilleur Jaccard).
    """
    resultats = []
    for i, (d, f) in enumerate(phrases_doc):
        indices = [n for n, m in enumerate(mots_doc) if d <= m[1] < f]
        if len(indices) < 6 or not all(analysable[n] for n in indices) or deja(indices):
            continue
        phrase = " ".join(mots_doc[n][0] for n in indices)
        g = grammes_lettres(phrase)
        taille = len(re.sub(r"[^a-z0-9]", "", phrase))
        if not g or taille < 25:
            continue
        pas = max(1, taille // 2)
        votes = Counter()
        for gramme in g:
            for position in index_src.get(gramme, ()):
                votes[position // pas] += 1
        meilleur = 0.0
        for case, _ in votes.most_common(3):
            for debut in (case * pas - pas, case * pas, case * pas + pas // 2):
                h = grammes_lettres(lettres_src[max(0, debut):max(0, debut) + taille])
                if h:
                    meilleur = max(meilleur, len(g & h) / len(g | h))
        if meilleur >= seuil:
            resultats.append((i, round(meilleur, 2)))
    return resultats


# ----------------------------------------------------------------------------- 3. décider
def meta_source(nom_fichier):
    """Auteur et année d'une source d'après son nom de fichier : Zhou_2016_CAM.pdf -> ("zhou", "2016").
    Un fichier nommé autrement n'a pas de métadonnées : la référence ne pourra pas être vérifiée."""
    m = re.match(r"([^\W\d_]+)_(\d{4})", nom_fichier)
    return (normaliser(m.group(1)), m.group(2)) if m else None


def reference_proche(texte, debut, fin, phrases, paragraphes, entre_guillemets, numerotee=False):
    """Cherche un appel de référence qui couvre le passage.
    - Citation entre guillemets : la référence doit suivre immédiatement (dans la phrase, ou juste après
      le guillemet fermant), ou introduire la citation (« Zhou et al. (2016) écrivent : “…” »).
    - Reformulation : une référence n'importe où dans le même paragraphe suffit (usage universitaire :
      une référence en fin de paragraphe couvre ce qui précède)."""
    phrase = next(((d, f) for d, f in phrases if d <= debut < f), (debut, fin))
    paragraphe = next(((d, f) for d, f in paragraphes if d <= debut < f), (debut, fin))
    if entre_guillemets:
        zone = (phrase[0], max(phrase[1], fin) + 30)
    else:
        zone = (paragraphe[0], paragraphe[1] + 30)
    return premier_appel(texte[zone[0]:zone[1]], numerotee)


def categorie(texte, debut, fin, phrases, paragraphes, source=None, retouche=False, n_mots=0, numerotee=False):
    """Un passage repris est-il une citation ? Trois questions : est-il entre guillemets, porte-t-il une
    référence, et cette référence désigne-t-elle bien la source où il a été retrouvé ?
    Tolérance : quelques mots repris tels quels (moins de 8) dans un paragraphe qui cite sa source,
    c'est une reformulation normale, pas une copie à signaler."""
    # entre guillemets si au moins 60 % du passage est couvert par des guillemets (une phrase qui commence
    # par « Selon lui, « … » » est une citation même si ses deux premiers mots sont dehors)
    couvert = sum(max(0, min(fin, g.end()) - max(debut, g.start())) for g in GUILLEMETS.finditer(texte))
    entre_guillemets = couvert >= 0.6 * (fin - debut)
    ref = reference_proche(texte, debut, fin, phrases, paragraphes, entre_guillemets, numerotee)
    if ref and source and meta_source(source) and ref["style"] in ("auteur-date", "auteur-page"):
        auteur, annee = meta_source(source)      # un appel numérique, une note ou « ibid. » ne se vérifie pas ici
        if auteur not in ref["auteurs"] and annee not in ref["annees"]:
            return "référence qui ne désigne pas la source"
    if retouche:
        return "reformulation citée" if ref else "copie retouchée"
    if entre_guillemets and ref:
        return "citation correcte"
    if entre_guillemets:
        return "guillemets sans référence"
    if ref:
        return "reformulation citée" if n_mots < CITATION_FORTE else "copie référencée sans guillemets"
    return "copie non citée"


# ----------------------------------------------------------------------------- tout assembler
def analyser(texte, sources, nom_document=""):
    """Compare un texte à des sources [(nom, texte, commun), ...] et retourne un dictionnaire de résultats.
    `commun` vaut True pour un texte que tout le monde a le droit de reprendre (énoncé, consignes).
    Une source qui porte le nom du document analysé est ignorée (c'est lui-même)."""
    mots, phrases, paragraphes = decouper_mots(texte), decouper_phrases(texte), decouper_paragraphes(texte)
    etiquette = [None] * len(mots)            # pour chaque mot : (catégorie, source) ou None
    zones = zones_ignorees(texte)
    biblio = next((z for z in zones if z[1] == len(texte)), None)
    numerotee = bool(biblio) and re.search(r"(?m)^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s+[A-ZÀ-Ý]", texte[biblio[0]:]) is not None
    for i, (_, debut, _) in enumerate(mots):
        if any(d <= debut < f for d, f in zones):
            etiquette[i] = ("zone ignorée", "titre, note ou bibliographie")
    analysable = [e is None for e in etiquette]
    appels_doc = [(a["debut"], a["fin"]) for a in appels(texte, numerotee)]
    dans_un_appel = frozenset(i for i, (_, debut, _) in enumerate(mots) if any(d <= debut < f for d, f in appels_doc))
    passages, remarques = [], []

    # expressions du domaine : un groupe de K mots présent dans au moins deux sources différentes n'appartient
    # à personne ; un passage court (moins de 8 mots) fait seulement de tels groupes n'est pas compté
    index = {nom: _index_source(texte_src) for nom, texte_src, commun in sources if not commun and nom != nom_document}
    presence = Counter()
    for nom in index:
        presence.update(index[nom][2].keys())
    partages = {g for g, n in presence.items() if n >= 2}
    courantes = 0

    def expression_courante(d, f):
        return f - d < CITATION_FORTE and all(tuple(m[0] for m in mots[i:i + K]) in partages for i in range(d, f - K + 1))

    # d'abord le texte commun autorisé (énoncé, consignes) : il est retiré du jeu
    for nom, texte_src, commun in [s for s in sources if s[2]]:
        for d, f in passages_identiques(mots, _index_source(texte_src)[2], analysable):
            for i in range(d, f):
                etiquette[i], analysable[i] = ("texte commun autorisé", nom), False
            passages.append({"debut": mots[d][1], "fin": mots[f - 1][2], "mots": f - d, "categorie": "texte commun autorisé",
                             "source": nom, "methode": f"{f - d} mots identiques à la suite", "score": 1.0, "confiance": "forte"})

    for nom, texte_src, commun in [s for s in sources if not s[2]]:
        if nom_document and nom == nom_document:
            remarques.append(f"{nom} porte le nom du document analysé : ignoré.")
            continue
        mots_src, phrases_src, positions_src, lettres_src, index_lettres, phrases_src_en_mots = index[nom]
        for d, f in passages_identiques(mots, positions_src, analysable):
            if expression_courante(d, f):
                courantes += 1
                continue
            debut, fin = mots[d][1], mots[f - 1][2]
            cat = categorie(texte, debut, fin, phrases, paragraphes, source=nom, n_mots=f - d, numerotee=numerotee)
            passages.append({"debut": debut, "fin": fin, "mots": f - d, "categorie": cat, "source": nom,
                             "methode": f"{f - d} mots identiques à la suite", "score": 1.0,
                             "confiance": "forte" if f - d >= CITATION_FORTE else "faible (passage court)"})
            for i in range(d, f):
                if etiquette[i] is None or GRAVITE[cat] < GRAVITE[etiquette[i][0]]:
                    etiquette[i] = (cat, nom)
        for i, j, score in phrases_retouchees(mots, phrases, phrases_src_en_mots, exclure=dans_un_appel):
            debut, fin = phrases[i]
            indices = [n for n, m in enumerate(mots) if debut <= m[1] < fin]
            if sum(1 for n in indices if not analysable[n] or etiquette[n] is not None) > len(indices) * 0.6:
                continue                      # déjà expliquée (copie mot pour mot, titre, texte commun)
            cat = categorie(texte, debut, fin, phrases, paragraphes, source=nom, retouche=True, numerotee=numerotee)
            d2, f2 = phrases_src[j]
            passages.append({"debut": debut, "fin": fin, "mots": len(indices), "categorie": cat, "source": nom,
                             "methode": f"vocabulaire presque identique (cosinus {score})", "score": score,
                             "source_extrait": texte_src[d2:f2].strip(), "confiance": "forte" if score >= 0.9 else "moyenne"})
            for n in indices:
                if etiquette[n] is None:
                    etiquette[n] = (cat, nom)
        deja = lambda indices: sum(1 for n in indices if etiquette[n] is not None) > len(indices) * 0.6
        for i, jaccard in passages_approximatifs(mots, phrases, lettres_src, index_lettres, analysable, deja):
            debut, fin = phrases[i]
            indices = [n for n, m in enumerate(mots) if debut <= m[1] < fin]
            cat = categorie(texte, debut, fin, phrases, paragraphes, source=nom, n_mots=len(indices), numerotee=numerotee)
            passages.append({"debut": debut, "fin": fin, "mots": len(indices), "categorie": cat, "source": nom,
                             "methode": f"ressemblance des lettres (Jaccard {jaccard}) : texte de la source abîmé par l'extraction",
                             "score": jaccard, "confiance": "forte" if jaccard >= 0.7 else "moyenne"})
            for n in indices:
                if etiquette[n] is None:
                    etiquette[n] = (cat, nom)

    juges = [e for e, ok in zip(etiquette, analysable) if ok or (e and e[0] not in ("zone ignorée", "texte commun autorisé"))]
    total = len(juges) or 1
    par_categorie = Counter(e[0] for e in etiquette if e)
    comptes = {cat: n for cat, n in par_categorie.items() if cat in GRAVITE and GRAVITE[cat] < 3}
    similaires = sum(comptes.values())
    plagiat = sum(n for cat, n in comptes.items() if GRAVITE[cat] < 2)
    citations = sum(n for cat, n in comptes.items() if GRAVITE[cat] == 2)
    par_source = Counter(e[1] for e in etiquette if e and e[0] in comptes)

    if par_categorie.get("zone ignorée"):
        remarques.append(f"{par_categorie['zone ignorée']} mots dans des titres, des notes ou une bibliographie : non jugés.")
    if par_categorie.get("texte commun autorisé"):
        remarques.append(f"{par_categorie['texte commun autorisé']} mots de texte commun (énoncé, consignes) : non comptés.")
    if courantes:
        remarques.append(f"{courantes} expression(s) courante(s) du domaine (présentes dans plusieurs sources) : non comptées.")
    if citations / total > PART_CITATIONS_MAX:
        remarques.append(f"Les citations correctes font {citations / total:.0%} du texte : correct, mais beaucoup ; "
                         "un travail ne doit pas être un collage de citations.")
    return {
        "n_mots": total, "n_mots_total": len(mots),
        "similarite_totale": round(similaires / total, 3),
        "plagiat_potentiel": round(plagiat / total, 3),
        "par_categorie": dict(par_categorie),
        "par_source": [{"nom": nom, "mots": n, "taux": round(n / total, 3)} for nom, n in par_source.most_common()],
        "passages": sorted(passages, key=lambda p: p["debut"]),
        "remarques": remarques,
        "etiquettes": etiquette, "mots": mots,
    }


def charger_corpus(dossier="corpus"):
    """Toutes les sources : (nom de fichier, contenu, commun). Les fichiers de corpus/commun/ sont du texte
    que tout le monde a le droit de reprendre (énoncé du devoir, consignes, définitions imposées)."""
    dossier = Path(dossier)
    sources = []
    for sous_dossier, commun in ((dossier, False), (dossier / "commun", True)):
        for p in sorted(sous_dossier.glob("*")):
            if p.suffix.lower() in (".txt", ".md", ".pdf", ".docx"):
                try:
                    sources.append((p.name, lire_fichier(p.name, p.read_bytes()), commun))
                except Exception as erreur:                 # un fichier illisible n'arrête pas l'analyse
                    print(f"Source ignorée : {erreur}")
    return sources


def afficher(resultat, texte):
    """Résumé lisible dans le terminal."""
    print(f"\n{resultat['n_mots']} mots jugés (sur {resultat['n_mots_total']})")
    print(f"Similarité totale : {resultat['similarite_totale']:.0%}   (tout ce qui ressemble à une source, citations comprises)")
    print(f"Plagiat potentiel : {resultat['plagiat_potentiel']:.0%}   (reprises sans citation correcte)")
    for cat, n in sorted(resultat["par_categorie"].items(), key=lambda x: -x[1]):
        print(f"  - {cat} : {n} mots")
    for s in resultat["par_source"]:
        print(f"Source {s['nom']} : {s['taux']:.0%} du document")
    for r in resultat["remarques"]:
        print(f"Remarque : {r}")
    print(f"\n{len(resultat['passages'])} passage(s) :")
    for p in resultat["passages"]:
        extrait = " ".join(texte[p["debut"]:p["fin"]].split())
        print(f"\n[{p['categorie']}] {p['methode']}, confiance {p['confiance']} — source : {p['source']}\n"
              f"  « {extrait[:160]}{'…' if len(extrait) > 160 else ''} »")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    document = lire_fichier(sys.argv[1], Path(sys.argv[1]).read_bytes())
    afficher(analyser(document, charger_corpus(), Path(sys.argv[1]).name), document)
    from style_ia import indice_ia                     # les deux critères complémentaires
    from references import coherence_references
    ia = indice_ia(document)
    print(f"\nIndice de style IA : {ia['indice'] if ia['indice'] is not None else '—'}/100 ({ia['niveau']}) — {ia['fiabilite']}")
    for m in ia["mesures"]:
        print(f"  - {m['nom']} : {m['valeur']} → {m['tendance']}")
    print("\nCohérence des références :")
    for r in coherence_references(document)["remarques"]:
        print(f"  - {r}")
