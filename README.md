# DiffusionPDF

Visionneuse PDF plein écran pour le tri manuel rapide d'un flux de documents :
les PDF déposés dans un répertoire `INPUT` sont affichés un par un, et
distribués au clavier vers trois répertoires de sortie (`LEFT`, `RIGHT`,
`SPACE`) sans souris, sans menu, sans outil — un pur « mode lecture ».

Application desktop Windows (PySide6/Qt), compilée en un exécutable
autonome (PyInstaller).

## Fonctionnement

1. L'application surveille le répertoire `INPUT` configuré et affiche les
   PDF détectés dans l'ordre chronologique de création (le plus ancien
   d'abord), dès que leur taille est stable (protection contre les fichiers
   encore en cours d'écriture par un scanner, un LIS, etc.). Les documents
   sont traités par lots (20 par défaut) : les nouveaux fichiers arrivés en
   cours de lot ne sont pris en compte qu'une fois le lot entièrement traité.
2. Le fichier suivant est préchargé en arrière-plan pendant que l'utilisateur
   consulte le document affiché, pour un enchaînement instantané.
3. Une des trois touches de distribution renomme (déplace, sans changer le
   nom) le fichier affiché vers le répertoire correspondant, puis affiche le
   suivant automatiquement.
4. L'application se ferme toute seule quand `INPUT` ne contient plus aucun
   PDF depuis `idle_timeout_seconds`, ou après ce même délai sans action de l'utilisateur (clavier
   ou souris). La taille et la position de la fenêtre ne sont jamais
   imposées : celles choisies par l'utilisateur sont mémorisées dans son
   profil Windows (`QSettings`) et reprises au lancement suivant.

### Raccourcis clavier

| Touche | Action |
|---|---|
| `Page suivante` / `Page précédente` / `↓` / `↑` | Navigation dans le document |
| `Ctrl` + `+` / `Ctrl` + `-` / `Ctrl` + `0` | Zoom avant / arrière / réinitialiser |
| `Ctrl` + `P` | Imprimer le document affiché |
| `←` | Déplacer le document vers `OUTPUT_LEFT` |
| `→` | Déplacer le document vers `OUTPUT_RIGHT` |
| `Espace` | Déplacer le document vers `OUTPUT_SPACE` |
| `F1` (relâchée) | Ouvrir le popup des emplacements (config + INPUT/OUTPUT_*) |

`←`/`→`/`Espace` déplacent immédiatement le document affiché, sans devoir
d'abord faire défiler jusqu'à sa dernière page.

La barre de titre affiche `[N] nom_du_fichier.pdf`, où `N` est le nombre de
PDF restants dans `INPUT`.

## Configuration

Chaque poste (utilisateur) a son propre fichier de configuration, créé
automatiquement au premier lancement :

- Windows : `%LOCALAPPDATA%\Promed\DiffusionPDF\config.toml`

Son emplacement est accessible depuis l'application via `F1` (utile en
support, notamment sur un poste dont on ne connaît pas la configuration).

Au premier démarrage, l'application crée ce fichier avec des valeurs par
défaut et affiche un message demandant de le compléter puis de relancer.
Exemple de contenu :

```toml
# Astuce : utilisez des slashes "/" dans les chemins, y compris sous
# Windows (ex. C:/Data/INPUT) — un antislash isolé n'est pas valide en TOML.

[paths]
input = "C:/Data/DiffusionPDF/INPUT"
output_left = "C:/Data/DiffusionPDF/OUTPUT_LEFT"
output_right = "C:/Data/DiffusionPDF/OUTPUT_RIGHT"
output_space = "C:/Data/DiffusionPDF/OUTPUT_SPACE"

[behavior]
stable_file_check_ms = 500              # intervalle de scan de INPUT
arrow_lock_seconds = 2.0                # délai pendant lequel ←/→ sont ignorées
idle_timeout_seconds = 60.0             # fermeture après inactivité (0 = jamais)
batch_size = 20                         # documents par lot (0 = pas de limite)
```

Les répertoires sont créés automatiquement s'ils n'existent pas.

## Installation (développement)

Prérequis : Python 3.11+, Windows.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m diffusion_pdf.app
```

## Compilation (exécutable autonome)

```powershell
.venv\Scripts\pip install -r requirements-build.txt
.\build.ps1
```

Génère `dist\DiffusionPDF-win64.exe`. L'icône de l'exécutable et de la
fenêtre est `packaging/assets/app.ico`, généré depuis
`packaging/assets/diffusionPDF.png` (à régénérer si l'image source change,
par exemple avec Pillow : `Image.open(...).save("app.ico", sizes=[(16,16),
(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])`).

## Installation en production

Pas d'installeur (MSI, etc.) : c'est un exécutable unique (`DiffusionPDF-win64.exe`),
produit par `.\build.ps1`.

### 1. Choisir l'emplacement — important

L'exécutable se met à jour lui-même en se remplaçant (voir plus bas), ce qui
demande un accès en écriture à son propre dossier **sans droits
administrateur**. Ne pas l'installer dans `C:\Program Files\` (protégé,
réservé aux admins) : les mises à jour silencieuses échoueraient.

Emplacement recommandé, propre à chaque utilisateur Windows :

```
%LOCALAPPDATA%\Programs\DiffusionPDF\DiffusionPDF-win64.exe
```

Au premier lancement, l'application crée elle-même un raccourci sur le
Bureau (icône de l'application incluse) — aucune action manuelle requise.
Idempotent : ne recrée pas le raccourci s'il existe déjà, y compris s'il a
été déplacé (seule sa suppression déclenche une recréation).

### 2. Premier lancement

- **Alerte SmartScreen** : l'exécutable n'est pas encore signé numériquement
  (pas de certificat de signature de code pour cette v1). Windows affichera
  *« Windows a protégé votre ordinateur »* au premier lancement — cliquer sur
  *Informations complémentaires* puis *Exécuter quand même*. Cette alerte ne
  réapparaît pas pour les lancements suivants de la même version.
- L'application crée le fichier de configuration du poste et affiche un
  message indiquant son emplacement, puis se ferme.
- Éditer ce fichier (voir [Configuration](#configuration)) avec les vrais
  chemins `INPUT` / `OUTPUT_LEFT` / `OUTPUT_RIGHT` / `OUTPUT_SPACE` du poste
  (chemins locaux ou partages réseau `\\serveur\partage\...`), puis relancer
  l'application.

### 3. Droits d'accès

Le compte Windows qui exécute l'application doit avoir les droits lecture
**et écriture** sur `INPUT` et sur les trois répertoires `OUTPUT_*` (le tri
déplace les fichiers). En cas de partage réseau, vérifier les permissions
NTFS et de partage, pas uniquement l'accès applicatif.

### 4. Lancement automatique à l'ouverture de session (optionnel)

Pour un poste dédié au tri, placer un raccourci vers l'exécutable dans le
dossier de démarrage de l'utilisateur (accessible via `Win+R` puis
`shell:startup`) pour que l'application démarre avec la session Windows.

### 5. Déploiement sur plusieurs postes

Chaque poste/utilisateur possède sa propre configuration
(`%LOCALAPPDATA%`) : il n'y a pas de configuration centralisée en v1.
Pour équiper plusieurs postes, répéter les étapes 1 à 3 sur chacun (ou
distribuer l'exécutable et un `config.toml` pré-rempli via votre outil de
déploiement habituel, par exemple un script de connexion ou une GPO).

## Mise à jour

Il n'y a pas de mise à jour automatique : pour changer de version, remplacer
l'exécutable `DiffusionPDF-win64.exe` (produit par `.\build.ps1`) sur chaque poste.

## Structure du projet

```
diffusion_pdf/
├── app.py                  # point d'entrée
├── config.py                # configuration par poste (TOML)
├── version.py                # source unique de la version
├── shortcut.py                # auto-création du raccourci Bureau
├── core/
│   ├── queue_manager.py      # file INPUT + détection fichier stable
│   ├── cache.py               # préchargement du document suivant
│   └── distributor.py         # déplacement vers OUTPUT_*
├── ui/
│   ├── pdf_view.py            # rendu, zoom, impression, touches
│   ├── main_window.py         # assemblage, distribution
│   └── locations_dialog.py    # popup F1 (emplacements)
packaging/
├── entrypoint.py              # point d'entrée dédié pour PyInstaller
├── diffusion_pdf.spec
└── assets/
    ├── diffusionPDF.png       # icône source
    └── app.ico                # icône multi-résolution (exe + fenêtre)
build.ps1                      # build + empreinte SHA-256
```
