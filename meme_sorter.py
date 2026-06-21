# -*- coding: utf-8 -*-
"""
Meme Sorter / Trieur de memes
=============================

A tiny, zero-dependency local web app to sort your memes by emotion.
Une petite application web locale, sans dependance, pour trier vos memes par emotion.

- Shows one meme at a time (photo OR video, with sound) and lets you file it
  into an emotion sub-folder with a single click or keystroke.
- NEVER deletes a file: it is only MOVED into a sub-folder.
- Works cross-platform (Windows, macOS, Linux).
- Folders and categories are configured in `config.json` (created on first run),
  and can be edited from inside the app (gear icon) or via the command line.

Run it:
    python meme_sorter.py
    python meme_sorter.py --source "/path/to/memes" --source "/another/path"
    python meme_sorter.py --port 8765 --lang en

Affiche un meme a la fois et permet de le classer dans un sous-dossier d'emotion
en un clic. Ne supprime jamais un fichier : il est seulement deplace.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

APP_NAME = "Meme Sorter"
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
REVIEW_FOLDER = "_To_review"  # where "Skip" sends files

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(HERE, "config.json")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".ogg", ".ogv", ".mkv", ".avi"}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT

MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".tiff": "image/tiff", ".avif": "image/avif",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".m4v": "video/mp4", ".ogg": "video/ogg", ".ogv": "video/ogg",
    ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
}

# Default categories: (name, keyboard key, emoji)
DEFAULT_CATEGORIES = [
    {"name": "Funny - LOL",            "key": "1", "emoji": "\U0001F602"},
    {"name": "Angry - Rage",           "key": "2", "emoji": "\U0001F621"},
    {"name": "Sad - Disappointed",     "key": "3", "emoji": "\U0001F622"},
    {"name": "Approval - Yes",         "key": "4", "emoji": "\U0001F44D"},
    {"name": "Celebration - Win",      "key": "5", "emoji": "\U0001F389"},
    {"name": "Shocked - WTF",          "key": "6", "emoji": "\U0001F631"},
    {"name": "Awkward - Cringe",       "key": "7", "emoji": "\U0001F62C"},
    {"name": "Sarcasm - Irony",        "key": "8", "emoji": "\U0001F643"},
    {"name": "Cute - Wholesome",       "key": "9", "emoji": "\U0001F970"},
]

DEFAULT_CONFIG = {
    "sources": [],
    "categories": DEFAULT_CATEGORIES,
    "port": DEFAULT_PORT,
    "host": DEFAULT_HOST,
    "language": "auto",  # "auto" | "en" | "fr"
}


# ---------------------------------------------------------------------------
#  Config management
# ---------------------------------------------------------------------------

class Config:
    def __init__(self, path: str):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                # Merge with defaults so missing keys are filled in.
                self.data = {**DEFAULT_CONFIG, **loaded}
            except (json.JSONDecodeError, OSError) as exc:
                print("WARNING: could not read %s (%s). Using defaults." % (self.path, exc))
                self.data = dict(DEFAULT_CONFIG)
        else:
            # First run: create a starter config file next to the script.
            self.save()
            print("Created a new config file: %s" % self.path)

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            print("WARNING: could not save config (%s)." % exc)

    # convenience accessors
    @property
    def sources(self):
        return self.data.get("sources", [])

    @sources.setter
    def sources(self, value):
        self.data["sources"] = value

    @property
    def categories(self):
        return self.data.get("categories", DEFAULT_CATEGORIES)

    @property
    def category_dirs(self):
        return {c["name"] for c in self.categories} | {REVIEW_FOLDER}


# ---------------------------------------------------------------------------
#  Filesystem helpers
# ---------------------------------------------------------------------------

def list_media(source: str, sort: str = "recent", exclude_dirs=None):
    """List media files directly inside `source` (not in already-sorted sub-folders)."""
    if not source or not os.path.isdir(source):
        return []
    out = []
    try:
        names = os.listdir(source)
    except OSError:
        return []
    for name in names:
        full = os.path.join(source, name)
        if os.path.isfile(full) and os.path.splitext(name)[1].lower() in MEDIA_EXT:
            out.append(full)
    if sort == "recent":
        out.sort(key=_safe_mtime, reverse=True)
    elif sort == "oldest":
        out.sort(key=_safe_mtime)
    elif sort == "name_desc":
        out.sort(key=lambda p: os.path.basename(p).lower(), reverse=True)
    else:  # "name"
        out.sort(key=lambda p: os.path.basename(p).lower())
    return out


def _safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def kind_of(path: str) -> str:
    return "video" if os.path.splitext(path)[1].lower() in VIDEO_EXT else "image"


def unique_dest(folder: str, filename: str) -> str:
    """Avoid overwriting an existing file by adding a _1, _2... suffix."""
    dest = os.path.join(folder, filename)
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(filename)
    i = 1
    while True:
        cand = os.path.join(folder, "%s_%d%s" % (base, i, ext))
        if not os.path.exists(cand):
            return cand
        i += 1


# ---------------------------------------------------------------------------
#  HTTP server
# ---------------------------------------------------------------------------

def make_handler(config: Config):
    undo_stack = []          # list of (current_path, origin_path)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "MemeSorter/1.0"

        def log_message(self, *a):
            pass  # silence

        # ---- response helpers ----
        def _json(self, obj, code=200):
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _html(self, html):
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _valid_source(self, sid):
            return 0 <= sid < len(config.sources)

        # ---- routing ----
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if route == "/":
                self._html(PAGE)
            elif route == "/api/config":
                self._api_config()
            elif route == "/api/sources":
                self._api_sources()
            elif route == "/api/next":
                self._api_next(qs)
            elif route == "/media":
                self._serve_media(qs)
            else:
                self.send_error(404)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = {}

            if route == "/api/move":
                self._do_move(data)
            elif route == "/api/undo":
                self._do_undo()
            elif route == "/api/sources/add":
                self._add_source(data)
            elif route == "/api/sources/remove":
                self._remove_source(data)
            else:
                self.send_error(404)

        # ---- API: config & sources ----
        def _api_config(self):
            self._json({
                "app_name": APP_NAME,
                "language": config.data.get("language", "auto"),
                "categories": config.categories,
                "review_folder": REVIEW_FOLDER,
                "configured": len(config.sources) > 0,
            })

        def _api_sources(self):
            res = []
            for i, s in enumerate(config.sources):
                res.append({
                    "id": i,
                    "path": s,
                    "exists": os.path.isdir(s),
                    "count": len(list_media(s)),
                })
            self._json({"sources": res})

        def _add_source(self, data):
            path = (data.get("path") or "").strip()
            if not path:
                self._json({"ok": False, "error": "empty_path"}, 400)
                return
            path = os.path.expanduser(path)
            if not os.path.isdir(path):
                self._json({"ok": False, "error": "not_a_folder"}, 400)
                return
            path = os.path.abspath(path)
            with lock:
                if path not in config.sources:
                    config.sources = config.sources + [path]
                    config.save()
            self._json({"ok": True})

        def _remove_source(self, data):
            sid = data.get("id")
            with lock:
                if isinstance(sid, int) and self._valid_source(sid):
                    new = list(config.sources)
                    new.pop(sid)
                    config.sources = new
                    config.save()
                    self._json({"ok": True})
                else:
                    self._json({"ok": False, "error": "bad_id"}, 400)

        # ---- API: media iteration ----
        def _category_counts(self, src):
            counts = {}
            for name in config.category_dirs:
                d = os.path.join(src, name)
                counts[name] = len(list_media(d)) if os.path.isdir(d) else 0
            return counts

        def _api_next(self, qs):
            sid = _int(qs.get("source", ["0"])[0])
            sort = qs.get("sort", ["recent"])[0]
            if not self._valid_source(sid):
                self._json({"done": True, "remaining": 0, "counts": {}})
                return
            src = config.sources[sid]
            files = list_media(src, sort)
            counts = self._category_counts(src)
            if not files:
                self._json({"done": True, "remaining": 0, "counts": counts,
                            "can_undo": len(undo_stack) > 0})
                return
            f = files[0]
            self._json({
                "done": False,
                "remaining": len(files),
                "name": os.path.basename(f),
                "kind": kind_of(f),
                "url": "/media?source=%d&file=%s" % (
                    sid, urllib.parse.quote(os.path.basename(f))),
                "can_undo": len(undo_stack) > 0,
                "counts": counts,
            })

        def _serve_media(self, qs):
            sid = _int(qs.get("source", ["0"])[0])
            fname = qs.get("file", [""])[0]
            if not self._valid_source(sid):
                self.send_error(404)
                return
            src = config.sources[sid]
            path = os.path.join(src, os.path.basename(fname))
            if not os.path.isfile(path):
                self.send_error(404)
                return
            ext = os.path.splitext(path)[1].lower()
            ctype = MIME.get(ext, "application/octet-stream")
            size = os.path.getsize(path)

            # Support Range requests (needed for smooth video playback / seeking).
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                try:
                    rng = range_header.split("=", 1)[1]
                    start_s, end_s = rng.split("-", 1)
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else size - 1
                    end = min(end, size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
                    self.send_header("Content-Length", str(length))
                    self.end_headers()
                    with open(path, "rb") as fh:
                        fh.seek(start)
                        self.wfile.write(fh.read(length))
                    return
                except (ValueError, OSError):
                    pass

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(path, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)

        # ---- API: move / undo ----
        def _do_move(self, data):
            with lock:
                sid = _int(data.get("source", 0))
                fname = os.path.basename(data.get("name", ""))
                category = data.get("category", "")
                if not self._valid_source(sid):
                    self._json({"ok": False, "error": "bad_source"}, 400)
                    return
                if category not in config.category_dirs:
                    self._json({"ok": False, "error": "unknown_category"}, 400)
                    return
                src = config.sources[sid]
                origin = os.path.join(src, fname)
                if not os.path.isfile(origin):
                    self._json({"ok": False, "error": "file_not_found"}, 404)
                    return
                target_dir = os.path.join(src, category)
                os.makedirs(target_dir, exist_ok=True)
                dest = unique_dest(target_dir, fname)
                try:
                    shutil.move(origin, dest)
                except OSError as exc:
                    self._json({"ok": False, "error": str(exc)}, 500)
                    return
                undo_stack.append((dest, origin))
                self._json({"ok": True})

        def _do_undo(self):
            with lock:
                if not undo_stack:
                    self._json({"ok": False, "error": "nothing_to_undo"})
                    return
                current, origin = undo_stack.pop()
                if os.path.isfile(current):
                    dest = unique_dest(os.path.dirname(origin), os.path.basename(origin))
                    try:
                        shutil.move(current, dest)
                    except OSError as exc:
                        self._json({"ok": False, "error": str(exc)}, 500)
                        return
                self._json({"ok": True})

    return Handler


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
#  Embedded web page (bilingual EN / FR)
# ---------------------------------------------------------------------------

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meme Sorter</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, "Segoe UI", Arial, sans-serif;
         background:#15171c; color:#e9ecf1; height:100vh; display:flex; flex-direction:column; }
  header { padding:10px 16px; background:#1d2027; display:flex; align-items:center; gap:14px;
           border-bottom:1px solid #2a2e37; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; font-weight:600; }
  .grow { flex:1; }
  .pill { background:#2a2e37; padding:4px 10px; border-radius:999px; font-size:13px;
          display:flex; align-items:center; gap:6px; }
  select, .btn { background:#2a2e37; color:#e9ecf1; border:1px solid #3a3f4b; border-radius:8px;
           padding:6px 10px; font-size:14px; cursor:pointer; }
  .btn:hover { background:#343a45; }
  main { flex:1; display:flex; min-height:0; }
  .stage { flex:1; display:flex; align-items:center; justify-content:center; padding:14px;
           min-width:0; position:relative; }
  .stage img, .stage video { max-width:100%; max-height:100%; object-fit:contain;
           border-radius:10px; background:#0c0d10; box-shadow:0 8px 30px rgba(0,0,0,.5); }
  .filename { position:absolute; bottom:6px; left:50%; transform:translateX(-50%);
           background:rgba(0,0,0,.55); padding:3px 10px; border-radius:8px; font-size:12px;
           max-width:90%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  aside { width:300px; background:#1a1d23; border-left:1px solid #2a2e37; padding:12px;
          overflow-y:auto; display:flex; flex-direction:column; gap:8px; }
  .cat { display:flex; align-items:center; gap:10px; width:100%; text-align:left;
         background:#262a33; color:#e9ecf1; border:1px solid #333845; border-radius:10px;
         padding:11px 12px; font-size:15px; cursor:pointer; transition:.08s; }
  .cat:hover { background:#30353f; transform:translateX(-2px); }
  .cat .key { background:#3a4150; border-radius:6px; min-width:26px; text-align:center;
         padding:2px 0; font-weight:700; font-size:13px; }
  .cat .em { font-size:20px; }
  .cat .nm { flex:1; }
  .cat .cnt { font-size:12px; color:#9aa3b2; }
  .controls { display:flex; gap:8px; margin-top:6px; }
  .controls button { flex:1; padding:10px; border-radius:10px; border:1px solid #333845;
         background:#262a33; color:#e9ecf1; cursor:pointer; font-size:14px; }
  .controls button:hover { background:#30353f; }
  #undo:disabled { opacity:.4; cursor:default; }
  .done { text-align:center; font-size:20px; opacity:.85; }
  .hint { font-size:12px; color:#8b93a3; margin-top:auto; line-height:1.5; }
  .flash { position:fixed; top:14px; left:50%; transform:translateX(-50%);
           background:#2e7d32; color:#fff; padding:8px 16px; border-radius:10px;
           opacity:0; transition:.2s; pointer-events:none; font-size:14px; z-index:50; }
  .flash.show { opacity:1; }
  /* Setup / settings overlay */
  .overlay { position:fixed; inset:0; background:rgba(8,9,12,.82); display:none;
             align-items:center; justify-content:center; z-index:100; padding:16px; }
  .overlay.show { display:flex; }
  .panel { background:#1d2027; border:1px solid #2e333d; border-radius:14px; width:560px;
           max-width:100%; max-height:90vh; overflow-y:auto; padding:22px; }
  .panel h2 { margin:0 0 4px; font-size:19px; }
  .panel p.sub { margin:0 0 16px; color:#9aa3b2; font-size:13px; }
  .src-row { display:flex; align-items:center; gap:8px; background:#262a33; border:1px solid #333845;
             border-radius:9px; padding:8px 10px; margin-bottom:8px; font-size:13px; }
  .src-row .p { flex:1; word-break:break-all; }
  .src-row .ok { color:#6cc36c; } .src-row .bad { color:#e07a7a; }
  .src-row button { background:#3a2f31; border:1px solid #6b4a4a; color:#ffb4b4; border-radius:7px;
             padding:4px 9px; cursor:pointer; }
  .addbar { display:flex; gap:8px; margin:10px 0 4px; }
  .addbar input { flex:1; background:#15171c; border:1px solid #3a3f4b; border-radius:8px;
             color:#e9ecf1; padding:9px 10px; font-size:13px; }
  .addbar button { background:#2e5d8c; border:1px solid #3a6ea5; color:#fff; border-radius:8px;
             padding:9px 14px; cursor:pointer; }
  .panel .close { margin-top:16px; width:100%; padding:11px; border-radius:10px; border:1px solid #333845;
             background:#262a33; color:#e9ecf1; font-size:15px; cursor:pointer; }
  .panel .close:disabled { opacity:.4; cursor:default; }
  .err { color:#e07a7a; font-size:12px; min-height:16px; margin-top:6px; }
</style>
</head>
<body>
<header>
  <h1 id="title">&#128451;&#65039; Meme Sorter</h1>
  <label class="pill" id="folderPill"><span data-i18n="folder">Folder</span>:
    <select id="source"></select>
  </label>
  <label class="pill" id="sortPill"><span data-i18n="order">Order</span>:
    <select id="sort">
      <option value="recent" data-i18n="newest">Newest first</option>
      <option value="oldest" data-i18n="oldest">Oldest first</option>
      <option value="name" data-i18n="az">Name A &#8594; Z</option>
      <option value="name_desc" data-i18n="za">Name Z &#8594; A</option>
    </select>
  </label>
  <span class="pill" id="remaining">&#8212;</span>
  <span class="grow"></span>
  <button class="btn" id="settingsBtn" title="Settings">&#9881;&#65039;</button>
  <button class="btn" id="langBtn">FR</button>
</header>
<main>
  <div class="stage" id="stage"></div>
  <aside id="cats"></aside>
</main>
<div class="flash" id="flash"></div>

<!-- Setup / Settings overlay -->
<div class="overlay" id="overlay">
  <div class="panel">
    <h2 data-i18n="setup_title">Set up your meme folders</h2>
    <p class="sub" data-i18n="setup_sub">Add the folders that contain your memes in bulk. Files are moved into emotion sub-folders inside each of these folders &#8212; nothing is ever deleted.</p>
    <div id="srcList"></div>
    <div class="addbar">
      <input id="srcInput" placeholder="C:\Users\you\Pictures\memes  or  /home/you/memes" />
      <button id="srcAdd" data-i18n="add">Add</button>
    </div>
    <div class="err" id="srcErr"></div>
    <button class="close" id="overlayClose" data-i18n="done_btn">Done</button>
  </div>
</div>

<script>
const I18N = {
  en: {
    folder:"Folder", order:"Order", newest:"Newest first", oldest:"Oldest first",
    az:"Name A → Z", za:"Name Z → A", remaining:(n)=> n+" left",
    allsorted:"🎉 Everything in this folder is sorted!",
    skip:"⏭ Skip", undo:"↩ Undo",
    hint_keys:"Keys: 1-9 = categories · P = skip · Z = undo.",
    hint_safe:"Nothing is deleted: files are moved into sub-folders.",
    setup_title:"Set up your meme folders",
    setup_sub:"Add the folders that contain your memes in bulk. Files are moved into emotion sub-folders inside each of these folders — nothing is ever deleted.",
    add:"Add", done_btn:"Done", missing:"[not found]",
    no_sources:"Add at least one folder to begin.",
    err_empty:"Please type a folder path.", err_notfound:"That folder does not exist.",
    moved:"→ ", skipped:"skipped → ", undone:"undone ✓",
    settings:"Settings",
  },
  fr: {
    folder:"Dossier", order:"Ordre", newest:"Plus récents d'abord", oldest:"Plus anciens d'abord",
    az:"Nom A → Z", za:"Nom Z → A", remaining:(n)=> n+" restant"+(n>1?"s":""),
    allsorted:"🎉 Tout est trié dans ce dossier !",
    skip:"⏭ Passer", undo:"↩ Annuler",
    hint_keys:"Touches : 1-9 = catégories · P = passer · Z = annuler.",
    hint_safe:"Rien n'est supprimé : les fichiers sont déplacés dans des sous-dossiers.",
    setup_title:"Configurez vos dossiers de memes",
    setup_sub:"Ajoutez les dossiers qui contiennent vos memes en vrac. Les fichiers sont déplacés dans des sous-dossiers d'émotion — rien n'est jamais supprimé.",
    add:"Ajouter", done_btn:"Terminé", missing:"[introuvable]",
    no_sources:"Ajoutez au moins un dossier pour commencer.",
    err_empty:"Saisissez un chemin de dossier.", err_notfound:"Ce dossier n'existe pas.",
    moved:"→ ", skipped:"passé → ", undone:"annulé ✓",
    settings:"Réglages",
  }
};

let LANG = 'en';
let SERVER_LANG = 'auto';
let SOURCE = 0, SORT = 'recent';
let CATS = [], CURRENT = null, CONFIGURED = false, REVIEW = '_To_review';

const $ = (id) => document.getElementById(id);
const stage=$('stage'), catsEl=$('cats'), remEl=$('remaining'),
      sel=$('source'), sortSel=$('sort'), flash=$('flash'),
      overlay=$('overlay'), srcList=$('srcList'), srcInput=$('srcInput'),
      srcErr=$('srcErr'), langBtn=$('langBtn');

function t(k){ return I18N[LANG][k]; }

function detectLang(){
  if (SERVER_LANG === 'en' || SERVER_LANG === 'fr') return SERVER_LANG;
  const saved = localStorage.getItem('meme_lang');
  if (saved === 'en' || saved === 'fr') return saved;
  return (navigator.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en';
}

function applyLang(){
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    if (I18N[LANG][k] && typeof I18N[LANG][k] === 'string') el.textContent = I18N[LANG][k];
  });
  langBtn.textContent = (LANG === 'en') ? 'FR' : 'EN';
  $('settingsBtn').title = t('settings');
  buildCats();
  renderRemaining();
}

function showFlash(msg){ flash.textContent=msg; flash.classList.add('show');
  setTimeout(()=>flash.classList.remove('show'),700); }

async function init(){
  const cfg = await (await fetch('/api/config')).json();
  CATS = cfg.categories; CONFIGURED = cfg.configured; SERVER_LANG = cfg.language;
  REVIEW = cfg.review_folder || '_To_review';
  LANG = detectLang();
  applyLang();
  await refreshSources();
  if (!CONFIGURED) { openOverlay(); }
  loadNext();
}

async function refreshSources(){
  const d = await (await fetch('/api/sources')).json();
  sel.innerHTML='';
  d.sources.forEach(s=>{
    const o=document.createElement('option');
    o.value=s.id;
    o.textContent = s.exists ? (s.path+'  ('+s.count+')') : (s.path+'  '+t('missing'));
    o.disabled=!s.exists;
    sel.appendChild(o);
  });
  const firstOk = d.sources.find(s=>s.exists);
  SOURCE = firstOk ? firstOk.id : (d.sources.length?0:-1);
  if (SOURCE>=0) sel.value=SOURCE;
  CONFIGURED = d.sources.length>0;
  renderSrcList(d.sources);
  return d.sources;
}

function buildCats(){
  catsEl.innerHTML='';
  CATS.forEach((c,i)=>{
    const b=document.createElement('button');
    b.className='cat';
    b.innerHTML='<span class="key">'+(c.key)+'</span><span class="em">'+c.emoji+
      '</span><span class="nm">'+c.name+'</span><span class="cnt" data-c="'+c.name+'">0</span>';
    b.onclick=()=>move(c.name);
    catsEl.appendChild(b);
  });
  const ctr=document.createElement('div'); ctr.className='controls';
  ctr.innerHTML='<button id="skip">'+t('skip')+'</button><button id="undo">'+t('undo')+'</button>';
  catsEl.appendChild(ctr);
  const hint=document.createElement('div'); hint.className='hint';
  hint.innerHTML=t('hint_keys')+'<br>'+t('hint_safe');
  catsEl.appendChild(hint);
  $('skip').onclick=skip; $('undo').onclick=undo;
}

function updateCounts(counts){
  document.querySelectorAll('[data-c]').forEach(el=>{
    el.textContent = counts[el.getAttribute('data-c')] ?? 0;
  });
}

let LAST_REMAINING = null;
function renderRemaining(){
  if (LAST_REMAINING === null) { remEl.textContent='—'; return; }
  remEl.textContent = t('remaining')(LAST_REMAINING);
}

async function loadNext(){
  if (SOURCE<0){ stage.innerHTML='<div class="done">'+t('no_sources')+'</div>';
    remEl.textContent='—'; return; }
  const d = await (await fetch('/api/next?source='+SOURCE+'&sort='+SORT)).json();
  updateCounts(d.counts||{});
  const undoBtn=$('undo'); if(undoBtn) undoBtn.disabled=!d.can_undo;
  if (d.done){ CURRENT=null; LAST_REMAINING=0; renderRemaining();
    stage.innerHTML='<div class="done">'+t('allsorted')+'</div>'; return; }
  CURRENT=d; LAST_REMAINING=d.remaining; renderRemaining();
  if (d.kind==='video'){
    stage.innerHTML='<video id="vid" src="'+d.url+'" controls autoplay loop playsinline></video>'+
      '<div class="filename">'+esc(d.name)+'</div>';
    const v=$('vid'); v.volume=0.6;
    v.play().catch(()=>{ v.muted=true; v.play().catch(()=>{}); });
  } else {
    stage.innerHTML='<img src="'+d.url+'"><div class="filename">'+esc(d.name)+'</div>';
  }
}

function esc(s){ return (s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function move(category){
  if(!CURRENT) return;
  const payload={source:SOURCE,name:CURRENT.name,category:category};
  CURRENT=null;
  const d=await (await fetch('/api/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
  if(d.ok) showFlash(t('moved')+category);
  loadNext();
}

async function skip(){
  if(!CURRENT) return;
  const payload={source:SOURCE,name:CURRENT.name,category:REVIEW};
  CURRENT=null;
  await fetch('/api/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  showFlash(t('skipped')+REVIEW);
  loadNext();
}

async function undo(){
  const d=await (await fetch('/api/undo',{method:'POST'})).json();
  if(d.ok) showFlash(t('undone'));
  loadNext();
}

/* ---- settings / setup overlay ---- */
function openOverlay(){ overlay.classList.add('show'); srcErr.textContent=''; refreshSources(); }
function closeOverlay(){ overlay.classList.remove('show'); refreshSources().then(loadNext); }

function renderSrcList(sources){
  srcList.innerHTML='';
  sources.forEach(s=>{
    const row=document.createElement('div'); row.className='src-row';
    row.innerHTML='<span class="p">'+esc(s.path)+'</span>'+
      '<span class="'+(s.exists?'ok':'bad')+'">'+(s.exists?('✓ '+s.count):'✕')+'</span>'+
      '<button data-rm="'+s.id+'">✕</button>';
    srcList.appendChild(row);
  });
  srcList.querySelectorAll('[data-rm]').forEach(b=>{
    b.onclick=async()=>{ await fetch('/api/sources/remove',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({id:parseInt(b.getAttribute('data-rm'))})});
      refreshSources(); };
  });
  const closeBtn=$('overlayClose'); if(closeBtn) closeBtn.disabled = sources.length===0;
}

async function addSource(){
  const path=srcInput.value.trim();
  srcErr.textContent='';
  if(!path){ srcErr.textContent=t('err_empty'); return; }
  const d=await (await fetch('/api/sources/add',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({path})})).json();
  if(d.ok){ srcInput.value=''; refreshSources(); }
  else { srcErr.textContent = d.error==='not_a_folder' ? t('err_notfound') : t('err_empty'); }
}

/* ---- events ---- */
sel.onchange=()=>{ SOURCE=parseInt(sel.value); loadNext(); };
sortSel.onchange=()=>{ SORT=sortSel.value; loadNext(); };
$('settingsBtn').onclick=openOverlay;
$('overlayClose').onclick=closeOverlay;
$('srcAdd').onclick=addSource;
srcInput.addEventListener('keydown',e=>{ if(e.key==='Enter') addSource(); });
langBtn.onclick=()=>{ LANG=(LANG==='en')?'fr':'en'; localStorage.setItem('meme_lang',LANG); applyLang(); };

document.addEventListener('keydown',(e)=>{
  if(e.target.tagName==='SELECT'||e.target.tagName==='INPUT') return;
  if(overlay.classList.contains('show')) return;
  if(e.key>='1'&&e.key<='9'){ const i=parseInt(e.key)-1; if(i<CATS.length) move(CATS[i].name); }
  else if(e.key.toLowerCase()==='p'){ skip(); }
  else if(e.key.toLowerCase()==='z'){ undo(); }
});

init();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
#  CLI / startup
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Meme Sorter - sort your memes by emotion, locally.")
    p.add_argument("--source", "-s", action="append", default=None,
                   help="A folder of memes to sort. Repeatable. Overrides config for this run.")
    p.add_argument("--config", "-c", default=DEFAULT_CONFIG_PATH,
                   help="Path to the config file (default: config.json next to this script).")
    p.add_argument("--port", "-p", type=int, default=None, help="Port to listen on.")
    p.add_argument("--host", default=None, help="Host/interface to bind (default 127.0.0.1).")
    p.add_argument("--lang", choices=["auto", "en", "fr"], default=None,
                   help="Force the interface language.")
    p.add_argument("--no-browser", action="store_true",
                   help="Do not open the web browser automatically.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    config = Config(args.config)

    # CLI overrides (do not persist unless it makes sense to).
    if args.source:
        cleaned = [os.path.abspath(os.path.expanduser(s)) for s in args.source]
        config.sources = cleaned
    if args.port:
        config.data["port"] = args.port
    if args.host:
        config.data["host"] = args.host
    if args.lang:
        config.data["language"] = args.lang

    host = config.data.get("host", DEFAULT_HOST)
    port = config.data.get("port", DEFAULT_PORT)

    handler = make_handler(config)
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as exc:
        print("ERROR: could not start server on %s:%d (%s)." % (host, port, exc))
        print("Another program may be using that port. Try: python meme_sorter.py --port 8800")
        _wait_to_exit()
        return 1

    url = "http://%s:%d/" % (host, port)
    bar = "=" * 60
    print(bar)
    print("  %s is running!" % APP_NAME)
    print("  Open your browser at: %s" % url)
    if not config.sources:
        print("  No folders configured yet - add them from the gear (settings) icon.")
    print("  (Close this window to stop the app.)")
    print(bar)

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping. Bye!")
    finally:
        server.server_close()
    return 0


def _wait_to_exit():
    try:
        input("\nPress Enter to quit...")
    except EOFError:
        pass


if __name__ == "__main__":
    sys.exit(main())
