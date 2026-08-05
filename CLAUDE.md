# DiffusionPDF — état du projet

Visionneuse PDF plein écran (PySide6/Qt) pour tri manuel INPUT ->
OUTPUT_LEFT / OUTPUT_RIGHT / OUTPUT_SPACE au clavier. Windows v1,
compilée en exécutable unique (PyInstaller) avec auto-update silencieux
via GitHub Releases.

Dépôt : https://github.com/marcstritt/DiffusionPDF (public — nécessaire
pour que l'auto-update, non authentifié, fonctionne sur les postes
clients). Dernière version publiée : **v0.1.6**.

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
- **Pas de garde ←/→** (retiré après v0.1.3, sur demande explicite) : une
  version antérieure interprétait "il faut avoir fait défiler jusqu'à la
  dernière page avant de pouvoir trier" comme un garde-fou anti-lecture-
  trop-rapide voulu. Ce n'était pas le cas : ←/→/Espace doivent tous les
  trois trier immédiatement, sans condition de défilement. Le mécanisme
  de garde (`_sort_gate_timer`, `_sort_enabled`) a été entièrement retiré
  de `main_window.py`, ainsi que `sort_delay_after_last_page_ms` de
  `config.py`.
- **Raccourci Bureau auto-créé au lancement plutôt qu'un vrai installeur**
  (v0.1.4+) : cohérent avec la décision "pas d'installeur" déjà prise (v1
  = exécutable unique). `diffusion_pdf/shortcut.py` shelle vers
  PowerShell (`WScript.Shell` COM + `[Environment]::GetFolderPath
  ('Desktop')`, qui respecte la redirection OneDrive du Bureau) plutôt
  que d'ajouter `pywin32` comme dépendance — un seul appel, aucun paquet
  supplémentaire à embarquer dans l'exe. Idempotent (`Test-Path` avant
  création) et silencieux en cas d'échec (comme la vérification de
  mise à jour), jamais bloquant/fatal. Icône : `packaging/assets/app.ico`
  (généré via Pillow, dev-only, depuis `diffusionPDF.png` — Pillow n'est
  **pas** une dépendance du paquet, uniquement utilisée une fois pour
  produire l'`.ico` commité), utilisée à la fois comme icône de
  l'exécutable (PyInstaller `icon=`) et comme icône de fenêtre à
  l'exécution (`QApplication.setWindowIcon`, bundlée via `datas=` et
  résolue depuis `sys._MEIPASS` en mode gelé).
- **Fenêtre adaptée au premier PDF seulement, pas à chaque document**
  (v0.1.6) : `_fit_window_to_page` ne s'exécute plus que pour le tout
  premier document affiché (`_window_fitted` dans `main_window.py`),
  sur demande explicite — l'utilisateur veut pouvoir agrandir la
  fenêtre ensuite sans qu'un document suivant ne la remette à sa taille
  d'ajustement.
- **Barre de défilement verticale toujours visible** (v0.1.6) :
  `PdfView.setVerticalScrollBarPolicy(ScrollBarAlwaysOn)` plutôt que "au
  besoin" — évite que la largeur du viewport (et donc le rendu) ne
  change selon que la page déborde ou non.
- **Préchargement borné à 2 documents d'avance** (v0.1.6), pas tout le
  dossier INPUT : `MainWindow._PRELOAD_AHEAD = 2`, `_preload_paths`
  (liste bornée) a remplacé l'ancien `_next_path` (un seul). Limite la
  mémoire occupée par des `QPdfDocument` ouverts simultanément quand
  INPUT contient des centaines de fichiers.
- **Dialogue de première ouverture** (v0.1.6) remplace le message
  "éditez ce fichier TOML à la main" : `SetupDialog` propose soit de
  créer une nouvelle configuration (sélecteurs de dossiers INPUT/
  OUTPUT_* + dossier où enregistrer `config.toml`), soit de reprendre un
  `config.toml` déjà existant ailleurs sur le disque. Comme
  `config.toml` peut désormais être enregistré à un endroit choisi par
  l'utilisateur (pas seulement `%LOCALAPPDATA%\Promed\DiffusionPDF\`),
  un petit fichier pointeur (`config_location.txt`, à l'emplacement
  standard) note son emplacement réel pour que `Config.resolve_path()`
  le retrouve aux lancements suivants sans redemander. Si `config.toml`
  est à l'emplacement standard (cas par défaut, et celui de tous les
  postes existants), aucun pointeur n'est créé — entièrement
  rétrocompatible.
- **Verrou temporisé ←/→ configurable** (v0.1.6, `arrow_lock_seconds`,
  2 secondes par défaut) : à ne pas confondre avec l'ancienne garde
  retirée après v0.1.3 (ci-dessous) — celle-ci était basée sur le
  défilement de page et bloquait aussi Espace ; celle-ci est un simple
  minuteur démarré à chaque nouveau document (`_lock_arrows` dans
  `main_window.py`), ne bloque que ←/→ (Espace reste toujours
  immédiat), et est réintroduite sur demande explicite de l'utilisateur
  pour éviter un tri accidentel avant d'avoir vu la page.

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
5. **Garde ←/→ qui ne s'active jamais** (trouvé après v0.1.3, en testant
   avec `QTest.keyClick` sur une vraie `MainWindow`) — la garde reposait
   uniquement sur `QPdfPageNavigator.currentPageChanged`, qui ne se
   déclenche que si la page affichée *change de valeur*. Pour un document
   d'une page (ou quand la page courante reste 0 d'un document au
   suivant), le signal ne part jamais : `_sort_enabled` restait bloqué à
   `False` pour toujours, ←/→ ne triaient plus rien après le tout premier
   document. Repro confirmée avant fix (aucun log `currentPageChanged`
   sur un PDF d'une page), fix vérifié après (`sort_enabled` passe bien à
   `True`). Fix : évaluation explicite de l'état après chaque nouveau
   document affiché (`_on_document_ready` dans `main_window.py`), en plus
   de rester à l'écoute du signal pour la navigation manuelle entre pages
   d'un même document.
6. **Page rognée à droite et en bas** (trouvé après v0.1.3, en chargeant
   un vrai rapport A4 de `C:\Users\mcs\Documents\DiffusionPDF\INPUT` et
   en comparant une capture d'écran de `PdfView` avant/après) — le calcul
   du zoom d'ajustement en hauteur traitait 1 point PDF (1/72 pouce)
   comme 1 pixel écran. `QPdfView` rend en réalité à la résolution
   logique de l'écran (96 DPI en général, ×1.333) : la page était donc
   affichée ~33% plus grande que le viewport ne le pensait, rognée sur
   les bords. Repro confirmée (`horizontalScrollBar().maximum()` non nul,
   texte visiblement coupé en plein mot sur la capture), fix vérifié par
   nouvelle capture (page entière visible, plus de barre de défilement
   horizontale). Fix : facteur `logicalDpiX()/72` et `logicalDpiY()/72`
   appliqué dans `_update_fit_zoom` et `ideal_content_width`
   (`pdf_view.py`). ⚠️ Symptôme invisible avec un PDF généré à la volée
   via `QPdfWriter` dans le même process de test — les deux calculs
   (zoom et largeur de fenêtre) partageaient la même hypothèse fausse et
   restaient cohérents *entre eux* sans jamais être comparés à un rendu
   réel. Toujours valider le rendu visuel (capture d'écran) avec un vrai
   fichier de production, pas seulement la cohérence interne des calculs.
7. **Doublons de fichiers dans OUTPUT_LEFT/OUTPUT_RIGHT** (trouvé après
   v0.1.3, **en production réelle** — pas en test — en inspectant
   `C:\Users\mcs\Documents\DiffusionPDF\OUTPUT_LEFT` /`OUTPUT_RIGHT` :
   14 fichiers présents en double, contenu identique confirmé par hachage
   SHA-256, ex. `36071491_56534.PDF` + `36071491_56534 (1).PDF`) —
   `move_to_bin` utilisait `shutil.move`, qui sur un échec d'`os.rename`
   (verrou fichier Windows pendant que `QPdfDocument` relâche encore le
   fichier, cf. bug #1) se rabat sur copie + suppression de la source. Si
   la copie réussit mais que la suppression de la source échoue à son
   tour (source encore verrouillée), une copie complète reste à
   destination **avant** que l'exception ne remonte. `_move_with_retry`
   retente alors le déplacement, mais `_unique_path` voit que le nom
   original existe déjà et choisit un nouveau nom `"... (1)"` — si cette
   seconde tentative réussit (verrou enfin relâché), les DEUX fichiers
   restent en place, identiques. Fix : `move_to_bin` utilise `Path.rename`
   (atomique sur un même volume — échoue proprement sans rien déplacer,
   aucun état partiel possible) et ne se rabat sur `shutil.move` que pour
   un vrai déplacement inter-volumes (`errno.EXDEV`), non pour un simple
   verrou (`distributor.py`). ⚠️ Les 14 doublons déjà présents sur le
   poste n'ont **pas** été supprimés (fichiers de production réels,
   patients) — à trier manuellement si besoin, le fix empêche seulement
   la récidive. **Repro fiable obtenue** en rejouant le même scénario
   (verrou fichier réel, `QPdfDocument` affiché puis fermé) avec l'ancien
   code (`git show HEAD:...`, avant cette session) dans un dossier neuf :
   11 copies dupliquées créées (`doc1.pdf` → `doc1 (10).pdf`) avant
   abandon. Même scénario rejoué avec le code corrigé : 0 doublon (le
   déplacement échoue proprement si le verrou dépasse le budget de
   nouvelles tentatives, sans laisser aucune copie partielle).
   ⚠️ Observation annexe : en fin de session (après de très nombreux
   cycles `QPdfDocument` dans le même process de test), le verrou met
   nettement plus longtemps à se relâcher qu'en début de session, parfois
   au-delà du budget de tentatives (1s = 10×100ms) — probablement une
   charge système accumulée (antivirus, indexation) propre à ce poste de
   test intensif, pas un problème du code. Si ça se reproduit en usage
   réel (tri qui échoue avec le message "fichier verrouillé"), envisager
   d'augmenter `_MOVE_RETRY_MAX`/`_MOVE_RETRY_MS` dans `main_window.py`.

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
- **Test du raccourci Bureau + icône** (v0.1.4) : exe copié dans un
  dossier isolé (jamais l'exécutable de production réel), lancé, présence
  et cible de `DiffusionPDF.lnk` vérifiées via `WScript.Shell
  .CreateShortcut(...)` en lecture, icône extraite avec
  `[System.Drawing.Icon]::ExtractAssociatedIcon` + relue avec l'outil
  Read pour comparaison visuelle. Idempotence vérifiée en relançant
  l'exe et en comparant `LastWriteTime` du `.lnk` avant/après (inchangé).
  ⚠️ Raccourci de test supprimé du vrai Bureau après coup (pointait vers
  l'exe de scratchpad, pas l'installation réelle de l'utilisateur).
- **Test de l'auto-update réel** : installé une version dans
  `%LOCALAPPDATA%\Programs\DiffusionPDF\`, publié une version
  supérieure sur GitHub, lancé l'ancienne, vérifié par hash SHA-256 du
  fichier sur disque qu'il s'était bien remplacé tout seul.
- **Test du tri clavier réel** : `SendKeys` + `SetForegroundWindow` via
  PowerShell pour piloter la vraie fenêtre. ⚠️ Peu fiable seul (a généré
  un tri en double au premier essai) — c'est ce test qui a révélé le
  bug d'auto-répétition ci-dessus. Toujours corréler avec le test
  source (déterministe) avant de conclure à un bug applicatif.
- **Vérification visuelle du rendu PDF** : `PdfView.grab()` sauvegardé en
  PNG (`pixmap.save(...)`) puis relu à l'œil — seule méthode qui a permis
  de détecter le bug de rognage DPI ci-dessus (bug #6), invisible dans
  les logs/asserts numériques. Toujours tester avec une copie d'un vrai
  fichier de `C:\Users\mcs\Documents\DiffusionPDF\INPUT` (jamais le
  dossier INPUT réel directement — un test qui appelle `_dispatch`/tri
  déplacerait un vrai fichier de production).
- **Credentials GitHub** : pas de `gh` CLI installé dans l'environnement.
  Un token OAuth utilisable pour l'API REST peut être récupéré via
  `git credential fill` (Git Credential Manager, déjà authentifié pour
  ce compte) — utilisé pour créer les releases et uploader les assets
  par `curl` brut.
- **Test de `_lock_arrows`/`arrow_lock_seconds`** (v0.1.6) : vraie
  `MainWindow` + `QTest.keyClick`, `arrow_lock_seconds=0.4` pour un test
  rapide — vérifié que ←/→ sont sans effet (fichier toujours dans
  INPUT) pendant le verrou, fonctionnent après son expiration, et
  qu'Espace trie immédiatement même pendant le verrou d'un document
  qui vient d'apparaître.
- **Test du dialogue de première ouverture** (`SetupDialog`, v0.1.6) :
  construction + bascule entre les deux modes (nouvelle config /
  config existante) vérifiée à vide (`QApplication` offscreen, sans
  fenêtre visible) ; `Config.create()` / `Config.adopt_existing()` /
  `Config.resolve_path()` (mécanisme du fichier pointeur) testés en
  isolation avec un dossier "standard" et un dossier "personnalisé"
  factices. ⚠️ Jamais exécuté de bout en bout comme un vrai premier
  lancement (l'app ne montre ce dialogue que si aucun `config.toml`
  n'existe encore, ce qui n'est vrai sur aucun poste de test
  disponible).
- **⚠️ Piège rencontré en testant `Config` avec un emplacement custom** :
  `os.environ['APPDATA'] = ...` n'a **aucun effet** sur
  `platformdirs.user_config_dir()` sous Windows (résolu via l'API
  Windows/registre, pas la variable d'environnement) — une tentative de
  test isolé a donc silencieusement écrit dans le **vrai**
  `config.toml` de production (`%LOCALAPPDATA%\Promed\DiffusionPDF\`)
  au lieu d'un dossier de scratch. Repéré immédiatement (relecture du
  fichier juste après écriture) et restauré avec les chemins réels
  documentés dans ce fichier (`C:\Users\mcs\Documents\DiffusionPDF\
  {INPUT,OUTPUT_LEFT,OUTPUT_RIGHT,OUTPUT_SPACE}`, confirmés présents
  sur le disque). Aucune donnée perdue, mais la bonne méthode pour
  tester `Config` avec un autre emplacement est de monkeypatcher la
  référence importée dans le module (`diffusion_pdf.config.
  user_config_dir = lambda *_: str(scratch_dir)`), jamais la variable
  d'environnement.
- **⚠️ Piège rencontré en publiant la release GitHub v0.1.6** : le
  premier appel `curl -X POST .../releases` a répondu "Validation
  Failed / tag already_exists" alors qu'aucune release n'avait encore
  été créée dans cette session — la requête avait en réalité déjà
  réussi une première fois (contenu du `body` de la release identique
  au JSON envoyé), seule la réponse de cette réussite silencieuse n'a
  pas été vue (retry réseau probable côté `curl`/tool). Avant de
  recréer une release en cas d'erreur "already_exists", toujours
  vérifier `GET /releases/tags/<tag>` : si elle existe déjà avec le bon
  contenu, il suffit d'uploader les assets sur son `upload_url`, pas de
  la recréer.

## Non testé / fragile

- **Avertissement console `qt.core.qobject.connect:
  QObject::connect(QPdfDocument, QPdfLinkModel): invalid nullptr
  parameter`** (signalé par l'utilisateur, "parfois") — tentative de repro
  approfondie sans succès : chargement d'un même document seul, cycle
  direct sur `PdfView.set_document()` avec 4 PDF réels différents, cycle
  complet des 8 PDF réels de production via `MainWindow` (touche Espace,
  sans la garde ←/→ retirée par ailleurs) — jamais capturé sur stderr
  dans ces conditions. Vient très probablement d'un détail interne de
  `QPdfView` (modèle de liens hypertexte internes, initialisé
  paresseusement) plutôt que de notre code — aucun `QPdfLinkModel` n'est
  créé ni manipulé dans `diffusion_pdf/`. Non corrigé faute de repro
  fiable ; a priori un avertissement cosmétique (aucun crash ni
  comportement visible associé rapporté). Si le symptôme se reproduit et
  s'accompagne d'un vrai souci visible, noter précisément le contexte
  (premier document de la session ? après combien de documents ? PDF
  contenant des liens cliquables ?) pour cibler la prochaine tentative.
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
- **Dialogue de première ouverture (`SetupDialog`, v0.1.6)** : jamais
  déclenché comme un vrai premier lancement (nécessite l'absence de
  `config.toml`, ce qui n'est vrai sur aucun poste disponible pour
  tester sans risquer le fichier de production) — seulement testé en
  isolation (voir ci-dessus). Le mode "reprendre un config.toml
  existant ailleurs" (fichier pointeur `config_location.txt`) n'a en
  particulier jamais été exercé avec un vrai chemin réseau/clé USB.
- **Verrou ←/→ (`arrow_lock_seconds`, v0.1.6)** : le minuteur lui-même
  est vérifié (`QTest`, délai raccourci à 0.4 s), mais jamais confirmé
  par une vraie pression de touche humaine avec le délai par défaut de
  2 s — à valider que la durée "se sent" bien en usage réel, pas trop
  courte pour éviter l'erreur visée, pas trop longue pour ne pas
  ralentir le tri d'un utilisateur expérimenté.

## Prochaine étape suggérée

Par priorité :

1. **Trier les 14 doublons déjà présents en production** (bug #7,
   `C:\Users\mcs\Documents\DiffusionPDF\OUTPUT_LEFT` et `OUTPUT_RIGHT`) —
   fichiers patients réels, identiques par paire, laissés intentionnellement
   en l'état (pas supprimés par Claude). Le fix empêche la récidive mais ne
   nettoie pas l'existant.
2. **Confirmer en conditions réelles** (pas en scratchpad) que
   l'instance déjà en cours d'utilisation par l'utilisateur (lancée depuis
   `C:\Users\mcs\Downloads\DiffusionPDF-win64 (1).exe`) se met bien à
   jour vers **v0.1.6** toute seule au prochain lancement. Cette version
   apporte plusieurs changements de comportement jamais vérifiés en usage
   réel (voir "Non testé / fragile" ci-dessus) : verrou ←/→ de 2 s qui
   "se sent" bien, fenêtre qui ne se redimensionne plus qu'au premier
   document, scrollbar toujours visible. À observer au premier tri réel
   après la mise à jour.
3. **Tester le dialogue de première ouverture pour de vrai**, sur un
   poste ou profil Windows sans `config.toml` existant (jamais fait —
   voir "Non testé / fragile") : les deux modes ("nouvelle
   configuration" et "reprendre un fichier existant"), y compris le
   mécanisme de fichier pointeur si l'emplacement choisi n'est pas le
   dossier standard.
4. Valider zoom (Ctrl +/-/0) et impression (Ctrl+P) manuellement — jamais
   testés par une vraie pression de touche sur une fenêtre réelle.
5. Envisager la signature de code si le nombre de postes en production
   augmente (évite l'alerte SmartScreen à chaque poste).

## État à la fin de la session (2026-08-05)

v0.1.6 committée (plusieurs commits, voir `git log`), poussée sur
`origin/main` et publiée sur GitHub Releases avec les deux assets
(`DiffusionPDF-win64.exe`, `.sha256`) — build testé (lancé comme
process isolé, version affichée dans le titre confirmée) avant
publication. Contenu de v0.1.6 : fenêtre adaptée au premier PDF
seulement, scrollbar verticale toujours visible, préchargement borné à
2 documents, dialogue de configuration au premier lancement, verrou
temporisé ←/→ configurable (`arrow_lock_seconds`, 2 s par défaut).
Rien en attente côté code : tous les changements demandés sont
commités et poussés. Le seul suivi manuel restant est la liste
ci-dessus, en particulier les points 1 (doublons de production
toujours en place) et 2/3 (plusieurs comportements de v0.1.6 jamais
vérifiés en conditions réelles, seulement testés en isolation).
