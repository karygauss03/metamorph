// Generated from Metamorph's registry (metamorph/registry.py). Do not edit by hand.
window.METAMORPH = window.METAMORPH || {};
window.METAMORPH.DATA = {
 "files": [
  {
   "name": "Vacation.heic",
   "ext": "heic",
   "kind": "image"
  },
  {
   "name": "Skyline.jpg",
   "ext": "jpg",
   "kind": "image"
  },
  {
   "name": "Product Launch.mov",
   "ext": "mov",
   "kind": "video"
  },
  {
   "name": "Podcast Intro.wav",
   "ext": "wav",
   "kind": "audio"
  },
  {
   "name": "Quarterly Report.pdf",
   "ext": "pdf",
   "kind": "pdf"
  },
  {
   "name": "Budget.xlsx",
   "ext": "xlsx",
   "kind": "sheet"
  }
 ],
 "kinds": {
  "image": {
   "label": "Image",
   "inputs": [
    "avif",
    "bmp",
    "gif",
    "heic",
    "jpg",
    "png",
    "svg",
    "tiff",
    "webp"
   ],
   "targets": [
    {
     "label": "JPG",
     "target": "jpg",
     "hint": "Convert to JPG"
    },
    {
     "label": "PNG",
     "target": "png",
     "hint": "Convert to PNG"
    },
    {
     "label": "WebP",
     "target": "webp",
     "hint": "Convert to WebP"
    },
    {
     "label": "HEIC",
     "target": "heic",
     "hint": "Convert to HEIC"
    },
    {
     "label": "TIFF",
     "target": "tiff",
     "hint": "Convert to TIFF"
    },
    {
     "label": "AVIF",
     "target": "avif",
     "hint": "Convert to AVIF"
    },
    {
     "label": "BMP",
     "target": "bmp",
     "hint": "Convert to BMP"
    },
    {
     "label": "PDF",
     "target": "pdf",
     "hint": "Convert to PDF"
    }
   ],
   "tools": [
    {
     "id": "tool:image:compress",
     "label": "Compress",
     "hint": "Smaller file, same format"
    },
    {
     "id": "tool:image:resize",
     "label": "Resize",
     "hint": "Scale by percent or width"
    },
    {
     "id": "tool:image:crop",
     "label": "Crop",
     "hint": "Draw the area to keep"
    },
    {
     "id": "tool:image:rotate",
     "label": "Rotate",
     "hint": "Turn 90° or 180°"
    },
    {
     "id": "tool:image:flip",
     "label": "Flip",
     "hint": "Mirror horizontally"
    },
    {
     "id": "tool:image:grayscale",
     "label": "Grayscale",
     "hint": "Black and white copy"
    },
    {
     "id": "tool:image:strip",
     "label": "Strip Info",
     "hint": "Remove EXIF, GPS and other metadata"
    },
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "AVIF",
    "BMP",
    "GIF",
    "HEIC",
    "JPG",
    "PNG",
    "SVG",
    "TIFF",
    "WebP"
   ],
   "writes": [
    "JPG",
    "PNG",
    "WebP",
    "HEIC",
    "TIFF",
    "AVIF",
    "BMP",
    "PDF"
   ],
   "extra": {
    "gif": [
     {
      "label": "MP4",
      "target": "mp4",
      "hint": "Convert to MP4"
     },
     {
      "label": "WebM",
      "target": "webm",
      "hint": "Convert to WebM"
     }
    ]
   }
  },
  "audio": {
   "label": "Audio",
   "inputs": [
    "aac",
    "aiff",
    "flac",
    "m4a",
    "mp3",
    "ogg",
    "opus",
    "wav",
    "wma"
   ],
   "targets": [
    {
     "label": "MP3",
     "target": "mp3",
     "hint": "Convert to MP3"
    },
    {
     "label": "M4A",
     "target": "m4a",
     "hint": "Convert to M4A"
    },
    {
     "label": "WAV",
     "target": "wav",
     "hint": "Convert to WAV"
    },
    {
     "label": "FLAC",
     "target": "flac",
     "hint": "Convert to FLAC"
    },
    {
     "label": "OGG",
     "target": "ogg",
     "hint": "Convert to OGG"
    },
    {
     "label": "OPUS",
     "target": "opus",
     "hint": "Convert to OPUS"
    },
    {
     "label": "AIFF",
     "target": "aiff",
     "hint": "Convert to AIFF"
    },
    {
     "label": "WMA",
     "target": "wma",
     "hint": "Convert to WMA"
    }
   ],
   "tools": [
    {
     "id": "tool:media:trim",
     "label": "Trim",
     "hint": "Cut to a time range"
    },
    {
     "id": "tool:media:split",
     "label": "Split",
     "hint": "Split at keyframes without re-encoding"
    },
    {
     "id": "tool:media:speed",
     "label": "Speed",
     "hint": "Speed up or slow down"
    },
    {
     "id": "tool:audio:compress",
     "label": "Compress",
     "hint": "128 kbps MP3"
    },
    {
     "id": "tool:audio:normalize",
     "label": "Normalize",
     "hint": "Even out loudness (EBU R128)"
    },
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "AAC",
    "AIFF",
    "FLAC",
    "M4A",
    "MP3",
    "OGG",
    "OPUS",
    "WAV",
    "WMA"
   ],
   "writes": [
    "MP3",
    "M4A",
    "WAV",
    "FLAC",
    "OGG",
    "OPUS",
    "AIFF",
    "WMA"
   ]
  },
  "video": {
   "label": "Video",
   "inputs": [
    "3gp",
    "avi",
    "flv",
    "mkv",
    "mov",
    "mp4",
    "mpeg",
    "mpg",
    "webm",
    "wmv"
   ],
   "targets": [
    {
     "label": "MP4",
     "target": "mp4",
     "hint": "Convert to MP4"
    },
    {
     "label": "MOV",
     "target": "mov",
     "hint": "Convert to MOV"
    },
    {
     "label": "MKV",
     "target": "mkv",
     "hint": "Convert to MKV"
    },
    {
     "label": "WebM",
     "target": "webm",
     "hint": "Convert to WebM"
    },
    {
     "label": "AVI",
     "target": "avi",
     "hint": "Convert to AVI"
    },
    {
     "label": "WMV",
     "target": "wmv",
     "hint": "Convert to WMV"
    },
    {
     "label": "GIF",
     "target": "gif",
     "hint": "Convert to GIF"
    },
    {
     "label": "MP3",
     "target": "mp3",
     "hint": "Convert to MP3"
    }
   ],
   "tools": [
    {
     "id": "tool:video:compress",
     "label": "Compress",
     "hint": "Smaller H.264 MP4"
    },
    {
     "id": "tool:media:trim",
     "label": "Trim",
     "hint": "Cut to a time range"
    },
    {
     "id": "tool:media:split",
     "label": "Split",
     "hint": "Split at keyframes without re-encoding"
    },
    {
     "id": "tool:video:mute",
     "label": "Mute",
     "hint": "Remove the audio track"
    },
    {
     "id": "tool:video:audio",
     "label": "Audio",
     "hint": "Extract the audio track without re-encoding"
    },
    {
     "id": "tool:video:rotate",
     "label": "Rotate",
     "hint": "Turn 90° or 180°"
    },
    {
     "id": "tool:video:resize",
     "label": "Resize",
     "hint": "Scale down to 1080p, 720p..."
    },
    {
     "id": "tool:media:speed",
     "label": "Speed",
     "hint": "Speed up or slow down"
    },
    {
     "id": "tool:audio:normalize",
     "label": "Normalize",
     "hint": "Even out loudness (EBU R128)"
    },
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "3GP",
    "AVI",
    "FLV",
    "MKV",
    "MOV",
    "MP4",
    "MPEG",
    "MPG",
    "WMV",
    "WebM"
   ],
   "writes": [
    "MP4",
    "MOV",
    "MKV",
    "WebM",
    "AVI",
    "WMV",
    "GIF",
    "MP3"
   ]
  },
  "pdf": {
   "label": "PDF",
   "inputs": [
    "pdf"
   ],
   "targets": [
    {
     "label": "DOCX",
     "target": "docx",
     "hint": "Convert to DOCX"
    },
    {
     "label": "ODT",
     "target": "odt",
     "hint": "Convert to ODT"
    },
    {
     "label": "PPTX",
     "target": "pptx",
     "hint": "Convert to PPTX"
    },
    {
     "label": "XLSX",
     "target": "xlsx",
     "hint": "Convert to XLSX"
    },
    {
     "label": "JPG",
     "target": "jpg",
     "hint": "Convert to JPG"
    },
    {
     "label": "PNG",
     "target": "png",
     "hint": "Convert to PNG"
    },
    {
     "label": "EPUB",
     "target": "epub",
     "hint": "Convert to EPUB"
    },
    {
     "label": "Text",
     "target": "txt",
     "hint": "Convert to Text"
    },
    {
     "label": "Markdown",
     "target": "md",
     "hint": "Convert to Markdown"
    }
   ],
   "tools": [
    {
     "id": "tool:pdf:compress",
     "label": "Compress",
     "hint": "Shrink images and streams"
    },
    {
     "id": "tool:pdf:split",
     "label": "Split",
     "hint": "One PDF per page or range"
    },
    {
     "id": "tool:pdf:extract",
     "label": "Pages",
     "hint": "Extract pages into a new PDF"
    },
    {
     "id": "tool:pdf:remove",
     "label": "Remove",
     "hint": "Delete pages"
    },
    {
     "id": "tool:pdf:rotate",
     "label": "Rotate",
     "hint": "Rotate every page"
    },
    {
     "id": "tool:pdf:images",
     "label": "Images",
     "hint": "Save every embedded image"
    },
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "PDF"
   ],
   "writes": [
    "DOCX",
    "ODT",
    "PPTX",
    "XLSX",
    "JPG",
    "PNG",
    "EPUB",
    "Text",
    "Markdown"
   ]
  },
  "document": {
   "label": "Document",
   "inputs": [
    "doc",
    "docx",
    "html",
    "md",
    "odt",
    "rtf",
    "txt"
   ],
   "targets": [
    {
     "label": "DOCX",
     "target": "docx",
     "hint": "Convert to DOCX"
    },
    {
     "label": "ODT",
     "target": "odt",
     "hint": "Convert to ODT"
    },
    {
     "label": "Markdown",
     "target": "md",
     "hint": "Convert to Markdown"
    },
    {
     "label": "Text",
     "target": "txt",
     "hint": "Convert to Text"
    },
    {
     "label": "EPUB",
     "target": "epub",
     "hint": "Convert to EPUB"
    },
    {
     "label": "HTML",
     "target": "html",
     "hint": "Convert to HTML"
    },
    {
     "label": "PDF",
     "target": "pdf",
     "hint": "Convert to PDF"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "DOC",
    "DOCX",
    "HTML",
    "Markdown",
    "ODT",
    "RTF",
    "Text"
   ],
   "writes": [
    "DOCX",
    "ODT",
    "Markdown",
    "Text",
    "EPUB",
    "HTML",
    "PDF"
   ]
  },
  "ebook": {
   "label": "Ebook",
   "inputs": [
    "epub"
   ],
   "targets": [
    {
     "label": "PDF",
     "target": "pdf",
     "hint": "Convert to PDF"
    },
    {
     "label": "DOCX",
     "target": "docx",
     "hint": "Convert to DOCX"
    },
    {
     "label": "ODT",
     "target": "odt",
     "hint": "Convert to ODT"
    },
    {
     "label": "Markdown",
     "target": "md",
     "hint": "Convert to Markdown"
    },
    {
     "label": "Text",
     "target": "txt",
     "hint": "Convert to Text"
    },
    {
     "label": "HTML",
     "target": "html",
     "hint": "Convert to HTML"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "EPUB"
   ],
   "writes": [
    "PDF",
    "DOCX",
    "ODT",
    "Markdown",
    "Text",
    "HTML"
   ]
  },
  "slides": {
   "label": "Slides",
   "inputs": [
    "odp",
    "ppt",
    "pptx"
   ],
   "targets": [
    {
     "label": "PDF",
     "target": "pdf",
     "hint": "Convert to PDF"
    },
    {
     "label": "JPG",
     "target": "jpg",
     "hint": "Convert to JPG"
    },
    {
     "label": "PNG",
     "target": "png",
     "hint": "Convert to PNG"
    },
    {
     "label": "PPTX",
     "target": "pptx",
     "hint": "Convert to PPTX"
    },
    {
     "label": "ODP",
     "target": "odp",
     "hint": "Convert to ODP"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "ODP",
    "PPT",
    "PPTX"
   ],
   "writes": [
    "PDF",
    "JPG",
    "PNG",
    "PPTX",
    "ODP"
   ]
  },
  "sheet": {
   "label": "Spreadsheet",
   "inputs": [
    "csv",
    "ods",
    "tsv",
    "xls",
    "xlsx"
   ],
   "targets": [
    {
     "label": "XLSX",
     "target": "xlsx",
     "hint": "Convert to XLSX"
    },
    {
     "label": "ODS",
     "target": "ods",
     "hint": "Convert to ODS"
    },
    {
     "label": "CSV",
     "target": "csv",
     "hint": "Convert to CSV"
    },
    {
     "label": "TSV",
     "target": "tsv",
     "hint": "Convert to TSV"
    },
    {
     "label": "PDF",
     "target": "pdf",
     "hint": "Convert to PDF"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "CSV",
    "ODS",
    "TSV",
    "XLS",
    "XLSX"
   ],
   "writes": [
    "XLSX",
    "ODS",
    "CSV",
    "TSV",
    "PDF"
   ]
  },
  "subtitle": {
   "label": "Subtitles",
   "inputs": [
    "srt",
    "vtt"
   ],
   "targets": [
    {
     "label": "SRT",
     "target": "srt",
     "hint": "Convert to SRT"
    },
    {
     "label": "VTT",
     "target": "vtt",
     "hint": "Convert to VTT"
    },
    {
     "label": "Text",
     "target": "txt",
     "hint": "Convert to Text"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    }
   ],
   "reads": [
    "SRT",
    "VTT"
   ],
   "writes": [
    "SRT",
    "VTT",
    "Text"
   ]
  },
  "archive": {
   "label": "Archive",
   "inputs": [
    "7z",
    "gz",
    "rar",
    "tar",
    "tar.gz",
    "zip"
   ],
   "targets": [
    {
     "label": "ZIP",
     "target": "zip",
     "hint": "Convert to ZIP"
    },
    {
     "label": "TAR",
     "target": "tar",
     "hint": "Convert to TAR"
    },
    {
     "label": "TAR.GZ",
     "target": "tar.gz",
     "hint": "Convert to TAR.GZ"
    }
   ],
   "tools": [
    {
     "id": "tool:any:zip",
     "label": "Zip",
     "hint": "Compress into a ZIP archive"
    },
    {
     "id": "tool:archive:extract",
     "label": "Extract",
     "hint": "Unpack next to the archive"
    }
   ],
   "reads": [
    "7Z",
    "GZ",
    "RAR",
    "TAR",
    "TAR.GZ",
    "ZIP"
   ],
   "writes": [
    "ZIP",
    "TAR",
    "TAR.GZ"
   ]
  }
 },
 "actions": [
  {
   "id": "action:share",
   "label": "Share",
   "hint": "Send to a phone or another device"
  },
  {
   "id": "action:float",
   "label": "Float",
   "hint": "Keep the file in a floating shelf"
  },
  {
   "id": "action:copy",
   "label": "Copy",
   "hint": "Copy the file to the clipboard"
  },
  {
   "id": "action:move",
   "label": "Move",
   "hint": "Move to another folder"
  },
  {
   "id": "action:path",
   "label": "Copy Path",
   "hint": "Copy the full path"
  },
  {
   "id": "action:terminal",
   "label": "Terminal",
   "hint": "Open a terminal here"
  }
 ],
 "aliases": {
  "jpeg": "jpg",
  "tif": "tiff",
  "heif": "heic",
  "aif": "aiff",
  "oga": "ogg",
  "htm": "html",
  "markdown": "md",
  "tgz": "tar.gz",
  "svgz": "svg",
  "m4v": "mp4"
 },
 "counts": {
  "conversions": 317,
  "conversionsWithoutWriterImpress": 297,
  "tools": 26,
  "actions": 6
 }
};
