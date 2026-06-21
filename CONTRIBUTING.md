# Contributing

Thanks for your interest in improving Meme Sorter! 🎉

## Ground rules

- The app is intentionally **zero-dependency** (Python standard library only).
  Please don't add third-party runtime dependencies without discussion.
- Keep it **cross-platform** (Windows, macOS, Linux). Use `os.path` / `pathlib`,
  never hardcode paths or path separators.
- The UI ships as a single embedded HTML string in `meme_sorter.py`. Keep all
  user-facing text in **both English and French** via the `I18N` table.

## Getting started

```bash
git clone https://github.com/<you>/meme-sorter.git
cd meme-sorter
python meme_sorter.py --source /path/to/some/test/memes
```

There's no build step. Edit `meme_sorter.py` and re-run.

## Submitting changes

1. Fork the repo and create a branch: `git checkout -b my-change`.
2. Make your change and test it manually with a folder of sample images/videos.
3. Open a pull request describing what you changed and why.

## Ideas / good first issues

- Drag-and-drop a folder onto the page to add it as a source.
- A "stats" view showing how many memes are in each category.
- Optional thumbnails / grid review mode.
- Configurable themes (light mode).
- Additional UI languages.

By contributing, you agree that your contributions are licensed under the MIT License.
