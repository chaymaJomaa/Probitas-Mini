# Probitas mini — un détecteur de plagiat 

Version pédagogique : **cinq fichiers Python** (`detecteur.py`, le moteur ; `formes_citation.py`, les normes de
citation ; `style_ia.py`, l'indice de style ; `references.py`, la cohérence des références ; `app.py`, la page
web), deux pages HTML et un dossier `tests/` de 31 textes à faire passer soi-même. Le but n'est pas de rivaliser avec Turnitin,
mais de comprendre, ligne par ligne, comment un détecteur de plagiat travaille, et d'y mettre une idée
d'éthique : distinguer une citation correcte d'une copie, et ne jamais accuser à tort.

## Installer et lancer (2 commandes, aucune installation lourde)

```powershell
python -m pip install --user flask pypdf python-docx
python app.py
```

Le navigateur s'ouvre sur http://127.0.0.1:5000. 
