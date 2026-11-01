# rne — Renaming studio

A Glosso port of the sibling [`rne`](../../../rne) bulk renamer, using the
standard `Terminal`, `Terminal/Editor`, `Regex`, `Time`, and `File_System`
modules. The application and regex engine are implemented in Glosso; Rust is
used only by the optional regex comparison harness.

The interface has editable Find/Replace panels, a live before/after changeset,
a recipe sidebar, a command palette, and an explicit apply review. Its ink,
teal, and amber palette and file-oriented layout are independent of chat TUIs.
The sidebar folds away below 120 columns, and fields stack below 84 columns.
The minimum interactive size is 52 columns by 20 rows.

## Build and run

From the Glosso repository root:

```sh
build/bin/glosso --std std -O3 examples/rne/main.glo -o build/rne
build/rne /path/to/files
build/rne -E -s 'IMG_(\d+)\.jpeg' -w 'photo-$1.jpg' /path/to/files
```

Interactive terminal support currently targets Linux and Windows. Use
`build/bin/glosso.exe` and `build/rne.exe` on Windows. `--help` lists the CLI
options. Read-only previews and explicit noninteractive application are also
available:

```sh
build/rne --preview -s 'draft' -w 'final' /path/to/files
build/rne --json -E -s 'track-(\d+)' -w 'song-$1' /path/to/files
build/rne --apply --yes -s 'draft' -w 'final' /path/to/files
build/rne --snapshot-ansi --width 120 --height 32 /path/to/files
```

`--preview`, `--json`, and snapshots never rename files. `--apply` requires
`--yes` and cannot be combined with a preview mode.

## Controls

| Key | Action |
| --- | --- |
| Tab / Shift+Tab | Focus Find, Replace, or the file list |
| Enter in an editor | Move to the next panel |
| Arrows, Home/End, Page Up/Down | Edit text or navigate the file list |
| Space / Enter in the list | Include or exclude the current entry |
| A / N / I in the list | Select all / none / invert |
| Ctrl+P | Open the recipe command palette |
| Ctrl+R / Ctrl+S / Ctrl+G | Regex / case sensitivity / all versus first match |
| Ctrl+A / Ctrl+T / Ctrl+E | Cycle name scope / case transform / automatic counter |
| Ctrl+U / Ctrl+F / Ctrl+D | Recursion / include files / include folders |
| Ctrl+W / Ctrl+K in an editor | Delete the preceding word / delete to the end |
| F5 | Refresh directory and metadata |
| F9 | Review the changeset; Cancel is initially selected |
| Left/Right, Enter in review | Choose and activate Cancel or Apply |
| Y / N in review | Apply / cancel |
| F1 | Show keys and variables |
| Esc | Dismiss the current overlay, or exit when none is open |
| Ctrl+Q / Ctrl+C | Dismiss an overlay, or exit |

Mouse clicks focus panels and select rows; clicking a row's selection marker
toggles it. The wheel navigates the list. On terminals providing bracketed-paste
events, paste inserts text only:
newlines and control characters are discarded, and pasted keys cannot confirm
a rename or invoke shortcuts. The Windows native console input path does not
provide bracketed-paste boundaries; see the [Terminal notes](../../std/Terminal/README.md).

## Transformations

Literal, case-insensitive, all-match replacement is the default. `-E` enables
[Regex](../../std/Regex/README.md), with `$0`, `$1`, `${name}`, and `$$` capture
expansions. Use braces to separate a capture from adjacent letters:
`${1}_photo`, rather than `$1_photo`. Literal mode keeps capture notation literal.

`--scope whole|name|ext` selects the part to transform. Leading dots belong to
the filename; directories have no extension. `--case` supports `keep`, `lower`,
`upper`, `title`, and `sentence`. Case conversion uses Unicode simple mappings
plus the common `ß` uppercase and `İ` lowercase expansions; it is not a
locale-sensitive or full contextual Unicode case-conversion engine.

Replacement variables work in both modes:

| Variable | Meaning |
| --- | --- |
| `$#`, `$##`, `$###` | Counter padded to the number of `#` characters |
| `${start=245,padding=4,increment=1}` | Counter with per-expression settings |
| `$parent` | Entry's immediate parent directory name |
| `$YYYY`, `$YY`, `$MMMM`, `$MMM`, `$MM` | Current year and month |
| `$DDDD`, `$DDD`, `$DD` | Current weekday and day |
| `$hh`, `$mm`, `$ss`, `$fff`, `$AMPM` | Current time; hours use a 24-hour clock |
| `$m.YYYY`, `$c.YYYY`, etc. | The same tokens from modification / creation time |

Dates use the local time zone when available and otherwise UTC. The current
time is fixed at refresh so the live preview stays stable. Missing filesystem
timestamps leave their variables literal. Month and weekday names are English.
Variables expand once, so `$` characters inside a parent name cannot introduce
capture expansions.

`--enumerate` appends a counter before the extension unless the replacement
already supplies a counter. `--start`, `--increment`, and `--padding` configure
it (defaults: 1, 1, 2). Counter indices follow the selected rows in the displayed
natural order, with directories first. Very large numeric runs sort without
integer overflow. Counters saturate at the signed 64-bit range.

`-r` scans subdirectories without following symlinks. `--files-only` and
`--dirs-only` filter entries. Symlinks, including dangling ones, are renamed as
entries rather than traversed. Recursion is bounded at 256 levels; an incomplete
scan disables application.

## Applying a plan

Empty names, path separators, control characters, duplicate targets, and
occupied destinations block the affected rows. Windows also rejects reserved
device names and forbidden characters. Exclude those rows or fix the recipe.
Apply rechecks conflicts and source identity before starting.

Renames use temporary sibling names and no-overwrite moves. This supports
swaps, cycles, and simultaneous parent/child renames. A failure reverses completed
moves; if reversal itself fails, the status reports paths for manual recovery.
The journal is in memory: the entire batch is **not crash-atomic**, and external
changes during application can still cause an operation or rollback to fail.
Windows collision keys are conservatively case-insensitive even on directories
configured for case-sensitive names.

## Verification

```sh
python3 tests/examples/rne.py build/bin/glosso
python3 tests/regex/check.py build/bin/glosso
python3 tests/regex/bench.py build/bin/glosso
```

The rne harness checks real filesystem transformations, collisions, cycles,
nested directories, symlinks, rollback, responsive snapshots, and a PTY session
covering Esc, Ctrl+S/Ctrl+Q, paste, resize, apply, and terminal restoration.
The regex harness compares results and timings with pinned Rust `regex`.

`Rename.glo` holds transformations, `App.glo` holds scanning and transactions,
`Ui.glo` renders and handles input, and `main.glo` provides CLI/session handling.
The original rne copyright and MIT terms are preserved in [LICENSE](LICENSE).
