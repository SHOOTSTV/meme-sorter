# 🗂️ Meme Sorter

A tiny, zero-dependency local web app to sort your memes by emotion. It shows
one meme at a time — photo **or** video (with sound) — and lets you file it into
an emotion sub-folder with a single click or keystroke.

**Nothing is ever deleted.** Files are only *moved* into sub-folders, and there's
an Undo button if you make a mistake.

> 🇫🇷 *Version française plus bas — [voir ci-dessous](#-français).*

![Python](https://img.shields.io/badge/python-3.8%2B-blue) ![No dependencies](https://img.shields.io/badge/dependencies-none-brightgreen) ![License: MIT](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- **Fast, keyboard-driven sorting** — press `1`–`9` to file the current meme, `P` to skip, `Z` to undo.
- **Photos and videos**, including video sound and seeking.
- **Safe by design** — files are moved, never deleted.
- **Configurable** — set your folders and emotion categories in `config.json`, or from the in-app ⚙️ settings panel.
- **Bilingual UI** (English / French) with a one-click toggle.
- **Cross-platform** — Windows, macOS, Linux.
- **Zero dependencies** — pure Python standard library. No `pip install` needed.

## Requirements

- [Python 3.8+](https://www.python.org/downloads/) (on Windows, tick *“Add Python to PATH”* during install).

## Quick start

1. Download or clone this repository.
2. Run it:
   - **Windows:** double-click `run.bat`
   - **macOS / Linux:** `./run.sh` (you may need `chmod +x run.sh` first)
   - **Any platform:** `python meme_sorter.py`
3. Your browser opens at `http://127.0.0.1:8765`.
4. On first run, the ⚙️ **settings** panel opens — paste the full path to a folder
   that contains your memes and click **Add**. Repeat for as many folders as you like.
5. Start sorting! Click an emotion (or press `1`–`9`).

Each emotion becomes a sub-folder *inside* your source folder, e.g.:

```
Pictures/memes/
├── (your unsorted memes here)
├── Funny - LOL/
├── Angry - Rage/
├── Cute - Wholesome/
└── _To_review/        ← where "Skip" puts files
```

## Configuration

A `config.json` file is created next to the script on first run. You can edit it
directly, copy [`config.example.json`](config.example.json), or use the in-app ⚙️ panel.

| Key | Meaning |
| --- | --- |
| `sources` | List of folders to sort (absolute paths). |
| `categories` | List of `{ "name", "key", "emoji" }`. `key` is the keyboard shortcut. |
| `port` | Local port (default `8765`). |
| `host` | Interface to bind (default `127.0.0.1`, i.e. your machine only). |
| `language` | `"auto"`, `"en"`, or `"fr"`. |

> `config.json` is git-ignored so your personal paths never get committed.

## Command-line options

```bash
python meme_sorter.py --source "/path/to/memes" --source "/another/folder"
python meme_sorter.py --port 8800
python meme_sorter.py --lang fr
python meme_sorter.py --no-browser
python meme_sorter.py --config /custom/config.json
```

`--source` overrides the configured folders for that run only.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `1`–`9` | Move the current meme to that emotion |
| `P` | Skip (moves it to `_To_review`) |
| `Z` | Undo the last move |

## How it works

`meme_sorter.py` runs a small local HTTP server (Python standard library only)
that serves a single-page web UI and streams your media files (with HTTP Range
support so videos seek smoothly). All processing stays on your computer — nothing
is uploaded anywhere.

## Privacy & safety

- Runs entirely **locally**; binds to `127.0.0.1` by default (not reachable from
  other machines).
- **Never deletes** files — only moves them, with Undo.
- Avoids overwriting: a name clash gets a `_1`, `_2`… suffix.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

---

## 🇫🇷 Français

**Trieur de memes** — une petite application web locale, sans dépendance, pour
trier vos memes par émotion. Elle affiche un meme à la fois (photo **ou** vidéo,
avec le son) et permet de le classer dans un sous-dossier d'émotion en un clic ou
une touche.

**Rien n'est jamais supprimé.** Les fichiers sont seulement *déplacés* dans des
sous-dossiers, et un bouton Annuler corrige les erreurs.

### Démarrage rapide

1. Téléchargez ou clonez ce dépôt.
2. Lancez :
   - **Windows :** double-cliquez sur `run.bat`
   - **macOS / Linux :** `./run.sh`
   - **Partout :** `python meme_sorter.py`
3. Le navigateur s'ouvre sur `http://127.0.0.1:8765`.
4. Au premier lancement, le panneau ⚙️ **réglages** s'ouvre : collez le chemin
   complet d'un dossier contenant vos memes et cliquez sur **Ajouter**.
5. Triez ! Cliquez sur une émotion (ou appuyez sur `1`–`9`).

### Raccourcis clavier

| Touche | Action |
| --- | --- |
| `1`–`9` | Classer le meme dans cette émotion |
| `P` | Passer (déplace vers `_To_review`) |
| `Z` | Annuler le dernier déplacement |

### Configuration

Un fichier `config.json` est créé à côté du script au premier lancement. Vous
pouvez le modifier, copier `config.example.json`, ou utiliser le panneau ⚙️.
Les clés : `sources` (dossiers à trier), `categories` (`name`, `key`, `emoji`),
`port`, `host`, `language` (`auto`/`en`/`fr`).

### Confidentialité

Tout reste **en local** sur votre ordinateur (écoute sur `127.0.0.1`). Aucun
fichier n'est supprimé ni envoyé sur Internet.

Licence : [MIT](LICENSE).
