# Feuille de tests — à remplir soi-même

Chaque fichier de ce dossier est un texte d'étudiant construit à partir des quatre articles du dossier `corpus/`
(Zhou 2016, Ghorbani 2019, Chowdhury 2024, Zhang 2025). Pour tester : lancer `python app.py`, déposer le
fichier sur la page (ou le glisser dans la zone), lire le verdict, les couleurs, les remarques, la cohérence des
références, puis noter ce que l'on observe et dire si la réponse de l'outil est celle qu'un relecteur attentif
donnerait. En console : `python detecteur.py tests/A01_copie_brute.txt`.

Les quatre familles : **A** ce que l'outil doit attraper · **B** ce qu'il ne doit pas accuser ·
**C** ce qu'il doit faire vérifier par un humain · **D** ce qu'il ne voit pas.

## A — des fautes

| N° | Fichier | Ce que contient le texte | Ce que j'observe (couleurs, %, source, remarques) | Réponse correcte ? Pourquoi ? |
| --- | --- | --- | --- | --- |
| A01 | `A01_copie_brute.txt` | l'abstract de CAPE recopié mot pour mot, sans guillemets ni référence | | |
| A02 | `A02_copie_retouchee.txt` | trois phrases de Zhou 2016 avec quelques mots changés et l'ordre un peu modifié, sans référence | | |
| A03 | `A03_reference_sans_guillemets.txt` | deux phrases de Ghorbani 2019 recopiées telles quelles, avec la référence en fin de paragraphe mais sans guillemets | | |
| A04 | `A04_guillemets_sans_reference.txt` | deux phrases de Zhang 2025 entre guillemets, sans aucune référence ni bibliographie | | |
| A05 | `A05_fausse_reference.txt` | une phrase de Zhou 2016 entre guillemets, attribuée à Ghorbani 2019 | | |
| A06 | `A06_patchwork.txt` | une phrase de chacun des quatre articles, reliées par des connecteurs, sans référence | | |
| A07 | `A07_pdf_abime.txt` | trois phrases de Zhou 2016 copiées depuis un lecteur PDF : mots coupés, ligatures perdues, numéro de page au milieu | | |
| A08 | `A08_reference_fantome.txt` | texte original, mais une référence (Selvaraju et al., 2017) citée dans le texte et absente de la bibliographie | | |
| A09 | `A09_auto_plagiat.txt` | un paragraphe repris du rapport de TP de l'étudiant (`corpus/Etudiant_2025_rapport_precedent.txt`), sans le dire | | |

## B — des textes corrects

| N° | Fichier | Ce que contient le texte | Ce que j'observe | Réponse correcte ? Pourquoi ? |
| --- | --- | --- | --- | --- |
| B10 | `B10_texte_original.txt` | un texte personnel sur le même sujet, une référence et sa bibliographie | | |
| B11a | `B11a_citation_APA.txt` | citation entre guillemets, norme APA : (Chowdhury et al., 2024, p. 1) | | |
| B11b | `B11b_citation_Harvard.txt` | citation introduite par « Zhou et al. (2016, p. 1) write that » | | |
| B11c | `B11c_citation_MLA.txt` | citation norme MLA : (Zhang et al. 9611) et « Works cited » | | |
| B11d | `B11d_citation_Vancouver.txt` | citation norme Vancouver : [1] et bibliographie numérotée | | |
| B11e | `B11e_citation_IEEE.txt` | citation norme IEEE : [1], entrées « [1] B. Zhou, … » | | |
| B11f | `B11f_citation_note.txt` | citation avec appel de note ¹ et note de bas de page « 1. Zhang, Z. et al., … » | | |
| B11g | `B11g_citation_ibid.txt` | deux citations, la seconde par (ibid., p. 1) | | |
| B12 | `B12_paraphrase_citee.txt` | idée de Ghorbani 2019 reformulée, quelques mots conservés, référence en fin de paragraphe | | |
| B13 | `B13_enonce_commun.txt` | l'énoncé du devoir recopié en tête (il est dans `corpus/commun/`), puis un texte original | | |
| B14 | `B14_titres_bibliographie.txt` | titres, sous-titres, texte original, et la bibliographie complète des quatre articles | | |
| B15 | `B15_formules_consacrees.txt` | texte original en anglais plein de tournures passe-partout (« in this paper, we propose », « to the best of our knowledge ») | | |
| B16 | `B16_termes_techniques.txt` | texte original plein de termes du domaine (class activation map, global average pooling, fine-grained…) | | |
| B17 | `B17_meme_sujet_independant.txt` | texte écrit indépendamment sur le même sujet que Finer-CAM, vocabulaire proche | | |

## C — des maladresses à faire vérifier

| N° | Fichier | Ce que contient le texte | Ce que j'observe | Réponse correcte ? Pourquoi ? |
| --- | --- | --- | --- | --- |
| C18 | `C18_annee_differente.txt` | citation correcte, mais l'appel dit 2015 et la bibliographie 2016 | | |
| C19 | `C19_normes_melangees.txt` | deux citations correctes, l'une en auteur-date, l'autre en numérique | | |
| C20 | `C20_entree_jamais_citee.txt` | bibliographie de quatre entrées, une seule citée dans le texte | | |
| C21 | `C21_citations_abusives.txt` | trois citations correctes qui font l'essentiel du texte | | |

## D — les limites

| N° | Fichier | Ce que contient le texte | Ce que j'observe | Qu'est-ce que l'outil ne peut pas voir, et pourquoi ? |
| --- | --- | --- | --- | --- |
| D22 | `D22_traduction.txt` | l'abstract de CAPE traduit mot à mot en français, sans référence | | |
| D23 | `D23_paraphrase_profonde.txt` | l'idée de Ghorbani 2019 entièrement réécrite, sans référence | | |
| D24 | `D24_texte_ia.txt` | un paragraphe au style typique d'un générateur de texte | | |
| D25 | `D25_source_absente.txt` | l'abstract de Ghorbani 2019 recopié ; **retirer d'abord `Ghorbani_2019_….pdf` du dossier `corpus/`** (le remettre après) | | |

## Tests à faire sans fichier

| Test | Comment faire | Ce que j'observe | Mon avis |
| --- | --- | --- | --- |
| Un vrai article contre les autres | déposer `corpus/Zhang_2025_Finer-CAM.pdf` lui-même sur la page (l'outil ignore la source qui porte le même nom) | | |
| Copier puis citer | coller l'abstract d'un des PDF ; puis le mettre entre guillemets avec (Auteur et al., année) et une ligne « Bibliographie » ; puis changer l'auteur de la référence | | |
| Un texte à moi | coller un paragraphe d'un de mes anciens devoirs | | |
