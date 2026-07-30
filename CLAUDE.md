# DiffusionPDF — état du projet

Visionneuse PDF plein écran (PySide6/Qt) pour tri manuel INPUT ->
OUTPUT_LEFT / OUTPUT_RIGHT / OUTPUT_SPACE au clavier. Windows v1,
compilée en exécutable unique (PyInstaller) avec auto-update silencieux
via GitHub Releases.

Dépôt : https://github.com/marcstritt/DiffusionPDF (public — nécessaire
pour que l'auto-update, non authentifié, fonctionne sur les postes
clients). Dernière version publiée : **v0.1.3**.

Le README.md documente l'usage, la configuration, le build et
l'installation en production — s'y référer pour tout ce qui est stable.
Ce fichier note plutôt le *pourquoi* des décisions et ce qui reste
fragile ou non testé.

## Décisions prises (et pourquoi)

- **QtPdf natif (`QPdfDocument`/`QPdfView`)** plutôt que PyMuPDF : PyMuPDF
  est en AGPL, problématique pour une distribution commerciale interne.
  QtPdf s'appuie sur pdfium (comme Chrome), licence Qt/LGPL propre.
- **Windows uniquement pour la v1** : évite la notarisation macOS
  (obligatoire sinon Gatekeeper bloque l'auto-update à chaque version).
- **GitHub Releases pour l'auto-update, dépôt public** : un appel API
  non authentifié échoue sur un dépôt privé (404) — le dépôt a été
  rendu public en cours de session précisément pour ça.
- **Emplacement d'install recommandé : `%LOCALAPPDATA%\Programs\...`**,
  jamais `C:\Program Files\` : l'auto-update se remplace lui-même sans
  droits admin, ce qui échouerait dans un dossier protégé.
- **Auto-update entièrement silencieux, appliqué dès qu'il est
  disponible** (pas de confirmation utilisateur) : cohérent avec la
  demande initiale de mises à jour automatiques, acceptable pour un
  outil interne. Le remplacement se fait par renommage à chaud
  (`os.replace` vers `.old` + déplacement du nouvel exe) sans helper
  externe — fonctionne car le bootloader PyInstaller onefile tourne
  depuis un dossier temp.
- **File d'attente par polling (QTimer), pas `watchdog`** : plus simple,
  un seul thread, suffisant vu qu'aucune latence temps réel n'est
  exigée. Un fichier n'est "prêt" qu'après deux scans consécutifs de
  taille identique (anti-fichier-en-cours-d'écriture).
- **Garde ←/→ (1s après la dernière page)** : interprétée comme un
  garde-fou anti-lecture-trop-rapide — il faut avoir fait défiler
  jusqu'à la dernière page avant de pouvoir trier avec ←/→. Espace n'est
  pas soumis à cette garde (comportement demandé explicitement).

## Bugs réels trouvés en testant (pas en relisant le code)

Tous corrigés, mais utiles à connaître si un symptôme similaire
réapparaît :

1. **Verrou fichier Windows** (fix initial, avant v0.1.0) —
   `QPdfDocument` garde le PDF affiché ouvert ; déplacer le fichier
   pendant l'affichage échouait silencieusement (copie ok, suppression
   de la source impossible). Fix : fermeture explicite du document
   (`close()`) avant tout déplacement + quelques tentatives de repli
   (`_move_with_retry` dans `main_window.py`).
2. **Import cassé dans l'exécutable compilé** (avant v0.1.0) —
   PyInstaller exécutait `app.py` comme script isolé, cassant les
   imports relatifs. Fix : point d'entrée dédié `packaging/entrypoint.py`
   qui importe `diffusion_pdf` comme un vrai package.
3. **Piège TOML** (avant v0.1.0) — un chemin Windows avec antislashs non
   échappés dans `config.toml` faisait planter l'appli silencieusement
   (pas de fenêtre, pas de message, `console=False`). Fix : config par
   défaut générée en slashes `/`, et `tomllib.TOMLDecodeError` transformé
   en message clair (`config.py`).
4. **Tri en double sur auto-répétition clavier** (v0.1.2) — une touche
   ←/→/Espace maintenue générait des événements d'auto-répétition non
   filtrés, chacun redéclenchant un tri. Trouvé en testant le tri manuel
   sur un poste réel avec de vrais PDF. Fix : `event.isAutoRepeat()`
   ignoré pour ces trois touches (`pdf_view.py`).

## Comment j'ai testé (utile pour la prochaine session)

- **Tests fonctionnels source** (pas committés dans le repo, vivent dans
  le scratchpad de session) : `QApplication` + `MainWindow` réels,
  `QTest.keyClick` pour simuler les touches, PDF générés à la volée via
  `QPdfWriter` (⚠️ toujours créer le `QApplication` AVANT `QPdfWriter`/
  `QPainter`, sinon crash natif silencieux — piège rencontré deux fois).
  Couvre : chargement, garde 1s, tri vers les 3 dossiers, fichier
  illisible, file vide.
- **Test de l'exécutable compilé réel** : build PyInstaller, lancé comme
  vrai process Windows (`tasklist`/`taskkill` depuis bash, titre de
  fenêtre lu via `Get-Process | Select MainWindowTitle` en PowerShell).
- **Test de l'auto-update réel** : installé une version dans
  `%LOCALAPPDATA%\Programs\DiffusionPDF\`, publié une version
  supérieure sur GitHub, lancé l'ancienne, vérifié par hash SHA-256 du
  fichier sur disque qu'il s'était bien remplacé tout seul.
- **Test du tri clavier réel** : `SendKeys` + `SetForegroundWindow` via
  PowerShell pour piloter la vraie fenêtre. ⚠️ Peu fiable seul (a généré
  un tri en double au premier essai) — c'est ce test qui a révélé le
  bug d'auto-répétition ci-dessus. Toujours corréler avec le test
  source (déterministe) avant de conclure à un bug applicatif.
- **Credentials GitHub** : pas de `gh` CLI installé dans l'environnement.
  Un token OAuth utilisable pour l'API REST peut être récupéré via
  `git credential fill` (Git Credential Manager, déjà authentifié pour
  ce compte) — utilisé pour créer les releases et uploader les assets
  par `curl` brut.

## Non testé / fragile

- **Zoom (Ctrl +/-/0) et impression (Ctrl+P)** : implémentés selon
  l'API Qt officielle (vérifiée via la doc Qt en ligne), mais jamais
  validés par une vraie pression de touche sur une fenêtre réelle.
- **Signature de code** : aucune. SmartScreen s'affiche au premier
  lancement de chaque poste (attendu, documenté dans le README).
- **Déploiement multi-postes** : pas de script central ; chaque poste a
  sa propre config (`%LOCALAPPDATA%`). À industrialiser si le nombre de
  postes grandit (GPO, script de connexion — voir README).
- **Comportement si `GITHUB_REPO` change de nom/propriétaire** :
  `diffusion_pdf/update/updater.py` a la constante en dur ; à mettre à
  jour manuellement si le dépôt est déplacé/renommé.

## Prochaine étape suggérée

Valider zoom/impression manuellement, puis envisager la signature de
code si le nombre de postes en production augmente (évite l'alerte
SmartScreen à chaque poste).
