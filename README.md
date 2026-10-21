<p align="center"><img src="data/metamorph.svg" width="128" alt="Metamorph logo"></p>

# Metamorph

An offline, zero-click file converter for Linux on X11, modeled on
[Tangerine for Mac](https://tangerineformac.com/). Drag any file, hold a key and
drop it on the format you want. Everything runs locally.

- **Shift** while dragging opens the **Convert** wheel
- **Alt** opens **Tools**: compress, resize, crop, trim, split, merge...
- **Ctrl** opens **Actions**: Share, Float, Copy, Move, Copy Path, Terminal

The wheel stays open after you let go of the key. Drop on a slice to apply it,
or drop in the middle (or press Esc) to cancel. Pressing another wheel key while
dragging switches wheels.

From the keyboard: select files in Files and press **F4**, or right-click and
choose Scripts > Metamorph. Use the arrow keys to choose, Enter to apply, Tab to
switch wheels and Esc to cancel. `metamorph open FILE...` works from any shell.

## Install

```sh
./install.sh              # or ./install.sh --no-autostart
nautilus -q               # once, so Files picks up the F4 shortcut
```

The installer needs no root. It creates `.venv` with the Python libraries,
including bundled ffmpeg and pandoc binaries when the system has none. It also
links `~/.local/bin/metamorph`, adds a menu entry and an "Open With" entry, adds
the Files script, and starts the watcher, by default at every login too.
`./uninstall.sh` reverses all of this.

System requirements: Python 3.12+, `python3-gi` with GTK 3 and `python3-xlib`,
all present on a stock Ubuntu 24.04 desktop.

## What it converts

`metamorph doctor` lists the backends it found and how many conversions they
enable. Converted files are saved next to the original as `name.ext`, or as
`name (2).ext` if that name is taken. Inputs with several pages or sheets
produce a folder.

| Kind | Reads | Writes |
|---|---|---|
| Images | JPG PNG WebP HEIC TIFF AVIF BMP GIF SVG | JPG PNG WebP HEIC TIFF AVIF BMP PDF (GIF also to MP4/WebM) |
| Audio | MP3 M4A WAV FLAC OGG Opus AIFF WMA AAC | MP3 M4A WAV FLAC OGG Opus AIFF WMA |
| Video | MP4 MOV MKV WebM AVI WMV MPG 3GP FLV | MP4 MOV MKV WebM AVI WMV GIF MP3 |
| PDF | PDF | DOCX ODT PPTX XLSX JPG PNG EPUB TXT Markdown (all pages, 300 DPI images) |
| Documents | DOCX DOC ODT Markdown TXT RTF HTML | DOCX ODT Markdown TXT EPUB HTML PDF |
| Ebooks | EPUB | PDF DOCX ODT Markdown TXT HTML |
| Slides | PPTX PPT ODP | PDF JPG PNG PPTX ODP |
| Spreadsheets | XLSX XLS ODS CSV TSV | XLSX ODS CSV TSV PDF |
| Subtitles | SRT VTT | SRT VTT TXT |
| Archives | ZIP TAR TAR.GZ GZ RAR 7Z | ZIP TAR TAR.GZ |

**26 tools**:

- **Images:** compress, resize, crop, rotate, flip, grayscale, strip metadata. Crop opens an
  editor: drag to select, resize from the handles, lock an aspect ratio, Fit to Content, arrow
  keys nudge (Shift for 10 px), Enter crops. With several images, the same area is cropped from each.
- **Video:** compress, trim, split, mute, extract audio, rotate, resize, change speed.
- **Audio:** compress, normalize loudness.
- **PDF:** compress, split, extract pages, remove pages, rotate, extract images.
- **Any selection:** merge (images or PDFs into one PDF, videos, audio, text) and zip.
- **Archives:** extract.

Optional system packages unlock more. Settings > Capabilities shows what's missing:

| Package | Adds |
|---|---|
| `libreoffice-writer` | `.doc` input; layout-faithful DOCX/ODT/RTF to PDF (otherwise pandoc and PyMuPDF lay out the PDF) |
| `libreoffice-impress` | every slide conversion |
| `libreoffice-calc` | XLS/ODS input, spreadsheet to ODS/PDF |
| `unrar` or `7zip` | RAR/7z input |

## Tangerine behavior vs. Linux design choices

There is no Tangerine binary to examine: it is sold only on the Mac App Store
for Apple-silicon Macs. This is a clean-room rebuild from its published
description.

| Tangerine (as published) | Metamorph |
|---|---|
| Shift / Command / Control during a drag | Shift / **Alt** / Ctrl. Super would open GNOME's Activities overview on release. All three keys can be changed in Settings. |
| Wheel appears while dragging in Finder | Watches X11's `XdndSelection` through XFixes, so it works with drags from any X11 app (Files, browsers, Electron apps...). |
| Select a file, press Enter | Files script on **F4**. Enter already opens files in Nautilus. |
| AirDrop | Share sends through KDE Connect, then Bluetooth, then a new e-mail with the attachment. |
| Pages export, RTFD and text clippings | Not offered (Apple-only formats). ODT is offered instead of Pages. |
| Conversion allowance (paid tiers) | None. Everything is free and unlimited. |

## Command line

```sh
metamorph to webp photo.heic          # convert
metamorph run tool:media:trim talk.mp4 -p start=1:00 -p end=2:30
metamorph run tool:image:crop a.jpg -p rect=0.1,0,0.9,1   # x0,y0,x1,y1 as fractions
metamorph list report.pdf             # what applies to a file
metamorph doctor                      # backends and counts
METAMORPH_DEBUG=1 metamorph           # log what the drag watcher sees
```

## Development

```sh
.venv/bin/python -m pytest tests -n auto
```

The tests generate a sample file in every input format. They run every
conversion and validate each output by decoding it (images open, media has
streams, PDFs have pages and so on), then run every tool. Conversions whose
backend isn't installed are skipped.

## Limitations

- X11 only for the global drag wheel. On Wayland, use the drop zone in Settings,
  the Files script or the CLI.
- A quick tap of Esc during a drag may be missed by the watcher. The drag
  source still cancels the drag and the wheel then closes.
- PDF to DOCX, XLSX and Markdown reconstruct structure heuristically, like any
  PDF converter. Scanned PDFs have no text to extract (there's no OCR).
