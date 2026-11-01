# rne — Renaming studio

A Glosso port of the sibling [`rne`](../../../rne) bulk renamer, using the
standard `Command_Line`, `Terminal`, `Terminal/Editor`, `Regex`, `Time`, and `File_System`
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

Arguments and help use the standard `Command_Line` specification. Pass option
values as separate arguments (`--search draft`); short flags can be grouped
(`-rEs 'draft(\d+)'`). Use `--` before a directory beginning with `-`.
String option values beginning with `-` (other than a single `-`) are rejected
by the standard parser; use the interactive editors for those search or
replacement strings. Repeating a switch keeps it enabled, and repeated value
options use their last value. `--files-only` and `--dirs-only` cannot be combined.

## Controls

| Key | Action |
| --- | --- |
| Tab / Shift+Tab | Focus Find, Replace, or the file list |
| Arrows, Home/End, Page Up/Down | Edit text or navigate the file list |
| Space in the list | Include or exclude the current entry |
| A / N / I in the list | Select all / none / invert |
| Ctrl+P | Open the recipe command palette |
| Ctrl+R / Ctrl+S / Ctrl+G | Regex / case sensitivity / all versus first match |
| Ctrl+A / Ctrl+T / Ctrl+E | Cycle name scope / case transform / automatic counter |
| Ctrl+U / Ctrl+F / Ctrl+D | Recursion / include files / include folders |
| Ctrl+W / Ctrl+K in an editor | Delete the preceding word / delete to the end |
| F5 | Refresh directory and metadata |
| F9 / Enter | Review the current edits from any panel; Cancel is initially selected |
| Left/Right, Enter in review | Choose and activate Cancel or Apply |
| Y / N in review | Apply / cancel |
| F1 | Show keys and variables |
| F2 | Inspect numbered regex captures; arrows / Page Up/Down scroll |
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
expansions. Numbered references consume only digits, so `$1_photo` and
`${1}_photo` both append `_photo` to capture 1. Use `${1}2` to append a literal
`2`; `$12` refers to capture 12. Literal mode keeps capture notation literal.

Regex mode shows a live numbered capture summary. F2 opens the filename and
first match, including `$0` (the whole match), each numbered group, and named
aliases. Move through the file list to inspect another filename. While editing,
an unrelated current row falls back to the first selected matching file. The
preview respects the name/extension scope and distinguishes unmatched optional
groups from empty captures.

Parentheses create captures; escaped parentheses match literal characters. For
example, Find `2번 배우 고세구 \((\d+)\)\.png` and Replace
`2번_배우_고세구_$1.png` turns `2번 배우 고세구 (12).png` into
`2번_배우_고세구_12.png`. With `\(\d+\)` instead, there is no `$1` group.

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
it (defaults: 1, 1, 2). Replacement counters advance only for selected files
matching Find within the chosen scope, in displayed natural order with
directories first. Unrelated and excluded rows do not consume numbers. A
matching file that already has its resulting name still consumes its number.
`${start=0}` therefore starts at `00` (or `0` with `padding=1`). Automatic
appended counters cover all selected entries. Very large numeric runs sort
without integer overflow. Counters saturate at the signed 64-bit range.

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

Run the CLI, replacement and capture-preview regressions from this checkout:

```sh
python3 tests/check.py /path/to/glosso --std /path/to/glosso/std
```

These build in a temporary directory and check CLI defaults, aliases, repeated
flags, invalid arguments, counters across mixed files, capture expansion,
preview/apply agreement, selection changes, and responsive capture details and
keyboard controls. On POSIX, a terminal test also checks Korean typing and paste,
F9 / Enter review, cancellation, confirmation, and terminal restoration. The
Glosso repository also provides the broader filesystem and terminal harnesses:

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
