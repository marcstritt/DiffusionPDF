# DiffusionPDF

Visionneuse PDF plein écran pour le tri manuel rapide d'un flux de documents :
les PDF déposés dans un répertoire `INPUT` sont affichés un par un, et
distribués au clavier vers trois répertoires de sortie (`LEFT`, `RIGHT`,
`SPACE`) sans souris, sans menu, sans outil — un pur « mode lecture ».

Application desktop Windows (PySide6/Qt), compilée en un exécutable
autonome (PyInstaller) avec mise à jour automatique via GitHub Releases.

## Fonctionnement

1. L'application surveille le répertoire `INPUT` configuré et affiche le
   premier PDF détecté, dès que sa taille est stable (protection contre les
   fichiers encore en cours d'écriture par un scanner, un LIS, etc.).
2. Le fichier suivant est préchargé en arrière-plan pendant que l'utilisateur
   consulte le document affiché, pour un enchaînement instantané.
3. Une des trois touches de distribution renomme (déplace, sans changer le
   nom) le fichier affiché vers le répertoire correspondant, puis affiche le
   suivant automatiquement.

### Raccourcis clavier

| Touche | Action |
|---|---|
| `Page suivante` / `Page précédente` / `↓` / `↑` | Navigation dans le document |
| `Ctrl` + `+` / `Ctrl` + `-` / `Ctrl` + `0` | Zoom avant / arrière / réinitialiser |
| `Ctrl` + `P` | Imprimer le document affiché |
| `←` | Déplacer le document vers `OUTPUT_LEFT` |
| `→` | Déplacer le document vers `OUTPUT_RIGHT` |
| `Espace` | Déplacer le document vers `OUTPUT_SPACE` |

**Garde de lecture** : `←` et `→` ne deviennent actives qu'une seconde après
l'affichage de la dernière page du document — impossible de trier un
document sans être allé au bout. `Espace` n'est pas soumis à cette garde et
reste actif immédiatement.

## Configuration

Chaque poste (utilisateur) a son propre fichier de configuration, créé
automatiquement au premier lancement :

- Windows : `%LOCALAPPDATA%\Promed\DiffusionPDF\config.toml`

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
sort_delay_after_last_page_ms = 1000   # délai de la garde ←/→
stable_file_check_ms = 500              # intervalle de scan de INPUT
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

Génère `dist\DiffusionPDF-win64.exe` ainsi que son empreinte
`dist\DiffusionPDF-win64.exe.sha256`.

## Mise à jour automatique

Au démarrage, l'application interroge silencieusement l'API GitHub
Releases du dépôt (voir `GITHUB_REPO` dans
`diffusion_pdf/update/updater.py`). Si une version plus récente est
disponible :

1. Le nouvel exécutable est téléchargé et son empreinte SHA-256 vérifiée.
2. L'exécutable courant est remplacé (via renommage à chaud, sans outil
   externe) et relancé automatiquement.
3. Aucune interaction utilisateur n'est requise ; la session de tri en
   cours n'est pas perdue (aucun fichier n'est déplacé pendant la mise à
   jour).

Pour publier une nouvelle version :

1. Mettre à jour `diffusion_pdf/version.py`.
2. Lancer `.\build.ps1`.
3. Créer une *release* GitHub avec le tag `vX.Y.Z` et y joindre
   `DiffusionPDF-win64.exe` et `DiffusionPDF-win64.exe.sha256`.

## Structure du projet

```
diffusion_pdf/
├── app.py                  # point d'entrée
├── config.py                # configuration par poste (TOML)
├── version.py                # source unique de la version
├── core/
│   ├── queue_manager.py      # file INPUT + détection fichier stable
│   ├── cache.py               # préchargement du document suivant
│   └── distributor.py         # déplacement vers OUTPUT_*
├── ui/
│   ├── pdf_view.py            # rendu, zoom, impression, touches
│   └── main_window.py         # assemblage, garde de lecture, distribution
└── update/
    └── updater.py             # vérification et application des mises à jour
packaging/
├── entrypoint.py              # point d'entrée dédié pour PyInstaller
└── diffusion_pdf.spec
build.ps1                      # build + empreinte SHA-256
```
