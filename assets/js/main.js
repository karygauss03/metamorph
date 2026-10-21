(() => {
const { DATA, icon, createWheel, MODES, MODE_TITLES } = window.METAMORPH;


const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ------------------------------------------------------------------ static bits

function renderIcons(root = document) {
  for (const span of $$("[data-icon]", root)) {
    span.outerHTML = icon(span.dataset.icon);
  }
}

function renderFormats() {
  const body = $("#formats-body");
  const order = ["image", "audio", "video", "pdf", "document", "ebook", "slides", "sheet", "subtitle", "archive"];
  body.innerHTML = order.map((k) => {
    const kind = DATA.kinds[k];
    return `<tr><th scope="row">${kind.label}</th><td>${kind.reads.join(" ")}</td><td>${kind.writes.join(" ")}</td></tr>`;
  }).join("");
  $("#conversion-count").textContent = DATA.counts.conversions;
  $("#count-note").textContent =
    `Without LibreOffice Writer and Impress it is ${DATA.counts.conversionsWithoutWriterImpress}, plus ${DATA.counts.tools} tools and ${DATA.counts.actions} actions either way.`;
}

// ------------------------------------------------------------------ files

const THUMBS = {
  "Vacation.heic": "assets/img/vacation.jpg",
  "Skyline.jpg": "assets/img/skyline.jpg",
  "Product Launch.mov": "assets/img/launch.jpg",
  "Quarterly Report.pdf": "assets/img/report.jpg",
};
const DOC_ICONS = {
  audio: "file-audio", video: "file-video", pdf: "file-text", document: "file-text", ebook: "file-text",
  slides: "file-text", sheet: "file-spreadsheet", subtitle: "captions", archive: "file-archive",
  image: "file-image", folder: "file-archive",
};
const ENCODERS = { jpg: "image/jpeg", png: "image/png", webp: "image/webp" };
const MIME_KIND = [[/^image\//, "image"], [/^video\//, "video"], [/^audio\//, "audio"], [/pdf$/, "pdf"],
  [/(spreadsheet|excel|csv)/, "sheet"], [/(presentation|powerpoint)/, "slides"],
  [/(word|opendocument\.text|markdown|text\/plain|rtf|html)/, "document"], [/epub/, "ebook"],
  [/(zip|tar|gzip|rar|7z)/, "archive"], [/(subrip|vtt)/, "subtitle"]];

let nextId = 1;
let files = [];
const blobUrls = new Set();

function canonical(ext) {
  return DATA.aliases[ext] || ext;
}

function extOf(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith(".tar.gz")) return "tar.gz";
  const i = lower.lastIndexOf(".");
  return i > 0 ? canonical(lower.slice(i + 1)) : "";
}

function kindOfExt(ext) {
  for (const [k, kind] of Object.entries(DATA.kinds)) if (kind.inputs.includes(ext)) return k;
  return null;
}

function baseName(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith(".tar.gz")) return name.slice(0, -7);
  const i = name.lastIndexOf(".");
  return i > 0 ? name.slice(0, i) : name;
}

function uniqueName(name) {
  if (!files.some((f) => f.name === name)) return name;
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  const stem = name.slice(0, name.length - ext.length);
  for (let n = 2; ; n++) {
    const candidate = `${stem} (${n})${ext}`;
    if (!files.some((f) => f.name === candidate)) return candidate;
  }
}

function makeFile({ name, kind, thumb = null, imageSrc = null, isNew = false }) {
  const ext = extOf(name);
  return { id: nextId++, name, ext, kind: kind || kindOfExt(ext) || "document", thumb, imageSrc, isNew };
}

function initialFiles() {
  return DATA.files.map((f) => makeFile({
    name: f.name, kind: f.kind, thumb: THUMBS[f.name] || null,
    imageSrc: f.kind === "image" ? THUMBS[f.name] : null,
  }));
}

function thumbHTML(file) {
  if (file.thumb) return `<span class="file__thumb"><img src="${file.thumb}" alt="" draggable="false"></span>`;
  const label = file.kind === "folder" ? "DIR" : file.ext.toUpperCase().slice(0, 4);
  return `<span class="file__thumb file__thumb--doc">${icon(DOC_ICONS[file.kind] || "file-text")}<span class="file__badge">${label}</span></span>`;
}

function renderFiles(focusId = null) {
  const list = $("#files");
  list.innerHTML = files.map((f) => `
    <li><button type="button" class="file${f.isNew ? " file--new" : ""}" data-id="${f.id}" data-selected="false"
      aria-label="${f.name}. Drag with Shift, Alt or Ctrl held, or press Enter for the wheel.">
      ${thumbHTML(f)}<span class="file__name">${f.name}</span></button></li>`).join("");
  files.forEach((f) => { f.isNew = false; });
  if (focusId) $(`.file[data-id="${focusId}"]`)?.focus();
}

function addFile(file) {
  file.isNew = true;
  files.push(file);
  renderFiles();
}

// ------------------------------------------------------------------ operations offered

function opsFor(file, mode) {
  if (mode === "action") return DATA.actions;
  if (file.kind === "folder") return mode === "tool" ? [{ id: "tool:any:zip", label: "Zip", hint: "Compress into a ZIP archive" }] : [];
  const kind = DATA.kinds[file.kind];
  if (!kind) return [];
  if (mode === "tool") return kind.tools;
  let targets = kind.targets.filter((t) => t.target !== file.ext);
  if (file.kind === "image" && kind.extra[file.ext]) targets = targets.concat(kind.extra[file.ext]);
  return targets;
}

// ------------------------------------------------------------------ hint line

const hint = $("#demo-help");
const HINTS = {
  idle: "Drag a file and hold <kbd>Shift</kbd>. Or focus a file and press <kbd>Enter</kbd>.",
  touch: "Tap <b>Convert</b>, <b>Tools</b> or <b>Actions</b> below, then drag a file.",
  dragging: "Now hold <kbd>Shift</kbd>, <kbd>Alt</kbd> or <kbd>Ctrl</kbd>. The wheel stays open when you let go of the key.",
  wheel: "Move onto a slice and drop. Drop in the middle or press <kbd>Esc</kbd> to cancel.",
  menu: "Arrow keys choose, <kbd>Enter</kbd> applies, <kbd>Tab</kbd> switches wheels, <kbd>Esc</kbd> closes.",
};
function setHint(key) { hint.innerHTML = HINTS[key]; }
const coarse = matchMedia("(pointer: coarse)").matches;
// The resting hint depends on the state: a toggled key, a touch screen, or a keyboard and mouse.
function restoreHint() {
  if (latched) hint.innerHTML = `${MODE_TITLES[latched]} is on. Now drag a file, and drop it on a slice.`;
  else setHint(coarse ? "touch" : "idle");
}

// ------------------------------------------------------------------ the wheel in the stage

const stage = $("#stage");
const layer = $("#wheel-layer");
let wheel = null;        // { api, mode, file, menu, x, y }

function openWheel(mode, file, clientX, clientY, { menu = false, external = false } = {}) {
  closeWheel();
  const items = opsFor(file, mode);
  const api = createWheel({ items, mode, idPrefix: "slice" });
  const root = api.root;
  if (menu) {
    root.tabIndex = 0;
    root.setAttribute("role", "menu");
    root.setAttribute("aria-label", `${MODE_TITLES[mode]} ${file.name}`);
    root.setAttribute("aria-orientation", "horizontal");
    api.slices.forEach((s) => {
      const option = document.createElement("span");
      option.id = `slice-${s.index}`;
      option.setAttribute("role", "menuitem");
      option.className = "visually-hidden";
      option.textContent = `${s.item.label}. ${s.item.hint || ""}`;
      root.append(option);
    });
    // Keep the ids unique: the SVG paths are decorative copies.
    root.querySelectorAll("path[id]").forEach((p) => p.removeAttribute("id"));
  }
  layer.hidden = false;
  layer.append(root);
  layer.style.pointerEvents = menu ? "auto" : "none";
  const rect = stage.getBoundingClientRect();
  const size = root.offsetWidth;
  const half = size / 2;
  const cx = Math.min(Math.max(clientX - rect.left, half), Math.max(half, rect.width - half));
  const cy = Math.min(Math.max(clientY - rect.top, half), Math.max(half, rect.height - half));
  root.style.left = `${cx}px`;
  root.style.top = `${cy}px`;
  wheel = { api, mode, file, menu, external };
  document.body.classList.add("is-wheel-open");
  syncHeldKeys(mode);
  if (menu) {
    if (api.slices.length) api.setHot(0);
    root.addEventListener("keydown", onMenuKey);
    root.focus();
    setHint("menu");
  } else {
    setHint("wheel");
  }
}

function closeWheel({ refocus = false } = {}) {
  if (!wheel) return;
  const file = wheel.file;
  wheel.api.root.remove();
  layer.hidden = true;
  layer.style.pointerEvents = "none";
  wheel = null;
  document.body.classList.remove("is-wheel-open");
  syncHeldKeys(null);
  if (refocus) $(`.file[data-id="${file.id}"]`)?.focus();
}

function chooseHot() {
  if (!wheel) return;
  const index = wheel.api.hot();
  const { file, mode } = wheel;
  const menu = wheel.menu;
  if (index === null) { closeWheel({ refocus: menu }); restoreHint(); return; }
  const op = wheel.api.slices[index].item;
  closeWheel({ refocus: menu });
  restoreHint();
  run(mode, op, file);
}

function onMenuKey(e) {
  if (!wheel) return;
  const n = wheel.api.slices.length;
  const hot = wheel.api.hot();
  const keyMode = { Shift: "convert", Alt: "tool", Control: "action" }[e.key];
  if (["ArrowRight", "ArrowDown"].includes(e.key) && n) wheel.api.setHot(hot === null ? 0 : (hot + 1) % n);
  else if (["ArrowLeft", "ArrowUp"].includes(e.key) && n) wheel.api.setHot(hot === null ? n - 1 : (hot - 1 + n) % n);
  else if (e.key === "Home" && n) wheel.api.setHot(0);
  else if (e.key === "End" && n) wheel.api.setHot(n - 1);
  else if (e.key === "Enter" || e.key === " ") chooseHot();
  else if (e.key === "Escape") { closeWheel({ refocus: true }); restoreHint(); }
  else if (e.key === "Tab") {
    const step = e.shiftKey ? -1 : 1;
    switchMenu(MODES[(MODES.indexOf(wheel.mode) + step + 3) % 3]);
  } else if (keyMode && keyMode !== wheel.mode && !e.repeat) switchMenu(keyMode);
  else return;
  e.preventDefault();
  e.stopPropagation();
}

function switchMenu(mode) {
  const { file } = wheel;
  const rect = wheel.api.root.getBoundingClientRect();
  openWheel(mode, file, rect.left + rect.width / 2, rect.top + rect.height / 2, { menu: true });
}

layer.addEventListener("pointermove", (e) => {
  if (wheel?.menu) wheel.api.setHot(wheel.api.hitTest(e.clientX, e.clientY));
});
layer.addEventListener("click", (e) => {
  if (!wheel?.menu) return;
  const index = wheel.api.hitTest(e.clientX, e.clientY);
  if (index === null) { closeWheel({ refocus: true }); restoreHint(); return; }
  wheel.api.setHot(index);
  chooseHot();
});

// ------------------------------------------------------------------ key toggles (touch) and held keys

let latched = null;
const keyButtons = $$(".key");
keyButtons.forEach((b) => b.addEventListener("click", () => {
  const mode = b.dataset.mode;
  latched = latched === mode ? null : mode;
  keyButtons.forEach((k) => k.setAttribute("aria-pressed", String(k.dataset.mode === latched)));
  restoreHint();
}));

function syncHeldKeys(mode) {
  keyButtons.forEach((k) => k.classList.toggle("is-held", k.dataset.mode === mode));
}

// ------------------------------------------------------------------ dragging files

const DRAG_THRESHOLD = 6;
let press = null;   // { file, el, x, y, id }
let drag = null;    // { file, el, ghost, x, y }

$("#files").addEventListener("pointerdown", (e) => {
  const el = e.target.closest(".file");
  if (!el || e.button !== 0) return;
  const file = files.find((f) => f.id === Number(el.dataset.id));
  press = { file, el, x: e.clientX, y: e.clientY, id: e.pointerId };
  el.setPointerCapture(e.pointerId);
});

$("#files").addEventListener("pointermove", (e) => {
  if (press && !drag && Math.hypot(e.clientX - press.x, e.clientY - press.y) > DRAG_THRESHOLD) startDrag(e);
  if (!drag) return;
  moveGhost(e.clientX, e.clientY);
  // Pointer events only open the first wheel; switching is driven by key presses
  // so that the newly pressed key wins even while another is still held.
  const mode = modeFromEvent(e);
  if (mode && !wheel) openWheel(mode, drag.file, e.clientX, e.clientY);
  if (wheel) wheel.api.setHot(wheel.api.hitTest(e.clientX, e.clientY));
});

$("#files").addEventListener("pointerup", (e) => {
  if (drag) {
    if (wheel && !wheel.menu && wheel.api.hot() !== null) chooseHot();
    else { closeWheel(); restoreHint(); }
    endDrag();
  } else if (press) {
    select(press.file);
  }
  press = null;
});

$("#files").addEventListener("pointercancel", () => { closeWheel(); endDrag(); press = null; restoreHint(); });

function modeFromEvent(e) {
  // A key newly held wins; a latched toggle (touch) opens the wheel straight away.
  if (e.shiftKey) return "convert";
  if (e.altKey) return "tool";
  if (e.ctrlKey || e.metaKey) return "action";
  return latched;
}

function startDrag(e) {
  const ghost = document.createElement("div");
  ghost.className = "ghost";
  ghost.innerHTML = thumbHTML(press.file);
  document.body.append(ghost);
  press.el.classList.add("is-dragging");
  drag = { file: press.file, el: press.el, ghost, x: e.clientX, y: e.clientY };
  moveGhost(e.clientX, e.clientY);
  setHint(latched ? "wheel" : "dragging");
}

function moveGhost(x, y) {
  drag.x = x;
  drag.y = y;
  drag.ghost.style.left = `${x}px`;
  drag.ghost.style.top = `${y}px`;
}

function endDrag() {
  if (!drag) return;
  drag.ghost.remove();
  drag.el.classList.remove("is-dragging");
  drag = null;
}

function select(file) {
  $$(".file").forEach((b) => { b.dataset.selected = String(Number(b.dataset.id) === file.id); });
}

window.addEventListener("keydown", (e) => {
  const mode = { Shift: "convert", Alt: "tool", Control: "action", Meta: "action" }[e.key];
  if (mode) syncHeldKeys(wheel?.mode || mode);
  if (!drag) return;
  if (mode) {
    e.preventDefault(); // stop Alt from focusing the browser menu
    if (!e.repeat && (!wheel || wheel.mode !== mode)) openWheel(mode, drag.file, drag.x, drag.y);
    if (wheel) wheel.api.setHot(wheel.api.hitTest(drag.x, drag.y));
  } else if (e.key === "Escape") {
    closeWheel();
    endDrag();
    press = null;
    restoreHint();
  }
});
window.addEventListener("keyup", (e) => {
  if (["Shift", "Alt", "Control", "Meta"].includes(e.key) && !wheel) syncHeldKeys(null);
  if (e.key === "Alt") e.preventDefault();
});
window.addEventListener("blur", () => syncHeldKeys(wheel?.mode || null));

// Keyboard path: Enter, Space or F4 on a file opens the wheel as a menu.
$("#files").addEventListener("keydown", (e) => {
  const el = e.target.closest(".file");
  if (!el || !["Enter", " ", "F4"].includes(e.key)) return;
  e.preventDefault();
  const file = files.find((f) => f.id === Number(el.dataset.id));
  select(file);
  const r = el.getBoundingClientRect();
  openWheel(latched || "convert", file, r.left + r.width / 2, r.top + r.height / 2, { menu: true });
});

// ------------------------------------------------------------------ dropping your own files

const dropHint = $("#dropzone-hint");
let external = null; // { kind, x, y }

function kindFromMime(type) {
  for (const [re, kind] of MIME_KIND) if (re.test(type)) return kind;
  return null;
}

stage.addEventListener("dragenter", (e) => {
  if (!e.dataTransfer?.types.includes("Files")) return;
  e.preventDefault();
  const item = e.dataTransfer.items?.[0];
  external = { kind: kindFromMime(item?.type || ""), mime: item?.type || "" };
  dropHint.hidden = false;
});

stage.addEventListener("dragover", (e) => {
  if (!external) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  const mode = e.shiftKey ? "convert" : e.altKey ? "tool" : (e.ctrlKey || e.metaKey) ? "action" : latched;
  if (mode && external.kind && (!wheel || wheel.mode !== mode)) {
    const ext = { image: "png", video: "mp4", audio: "mp3", pdf: "pdf", sheet: "xlsx", slides: "pptx",
      document: "docx", ebook: "epub", archive: "zip", subtitle: "srt" }[external.kind];
    openWheel(mode, makeFile({ name: `dropped.${ext}`, kind: external.kind }), e.clientX, e.clientY, { external: true });
    dropHint.hidden = true;
  }
  if (wheel?.external) wheel.api.setHot(wheel.api.hitTest(e.clientX, e.clientY));
});

stage.addEventListener("dragleave", (e) => {
  if (stage.contains(e.relatedTarget)) return;
  external = null;
  dropHint.hidden = true;
  if (wheel?.external) closeWheel();
});

stage.addEventListener("drop", async (e) => {
  if (!external) return;
  e.preventDefault();
  dropHint.hidden = true;
  const dropped = e.dataTransfer.files?.[0];
  const hotOp = wheel?.external && wheel.api.hot() !== null ? { mode: wheel.mode, op: wheel.api.slices[wheel.api.hot()].item } : null;
  closeWheel();
  external = null;
  if (!dropped) return;
  const url = URL.createObjectURL(dropped);
  blobUrls.add(url);
  const decodable = dropped.type.startsWith("image/") && await canDecode(url);
  const file = makeFile({ name: uniqueName(dropped.name), kind: kindFromMime(dropped.type) || kindOfExt(extOf(dropped.name)),
    thumb: decodable ? url : null, imageSrc: decodable ? url : null });
  addFile(file);
  if (hotOp) run(hotOp.mode, hotOp.op, file);
});

function canDecode(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = url;
  });
}

// ------------------------------------------------------------------ running operations

const toasts = $("#toasts");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const DURATION = { image: 900, audio: 1500, video: 2600, pdf: 1700, document: 1300, ebook: 1400, slides: 1900,
  sheet: 1000, subtitle: 500, archive: 900, folder: 700 };

function toast(title, { progress = true } = {}) {
  const li = document.createElement("li");
  li.className = "toast";
  li.innerHTML = `<div class="toast__head">${icon("loader-circle", "icon spin")}<span>${title}</span></div>
    <p class="toast__status">Working</p>${progress ? '<div class="toast__bar"><span></span></div>' : ""}
    <div class="toast__actions" hidden></div>`;
  toasts.append(li);
  while (toasts.children.length > 2) toasts.firstElementChild.remove();
  const api = {
    progress(f) { const bar = $(".toast__bar span", li); if (bar) bar.style.width = `${Math.round(f * 100)}%`; },
    done(message, { download = null, error = false } = {}) {
      li.classList.add(error ? "is-error" : "is-done");
      $(".toast__head .icon", li).outerHTML = icon(error ? "x" : "check");
      $(".toast__status", li).textContent = message;
      $(".toast__bar", li)?.remove();
      if (download) {
        const actions = $(".toast__actions", li);
        actions.hidden = false;
        actions.innerHTML = `<a class="button button--ghost button--small" href="${download.url}" download="${download.name}">${icon("download")}<span>Download</span></a>`;
      }
      setTimeout(() => li.remove(), download ? 12000 : 5000);
    },
  };
  return api;
}

async function animate(t, ms) {
  const steps = Math.max(6, Math.round(ms / 60));
  for (let i = 1; i <= steps; i++) { t.progress(i / steps); await sleep(ms / steps); }
}

async function run(mode, op, file) {
  if (mode === "action") return runAction(op, file);
  if (mode === "tool" && op.id === "tool:image:crop" && file.imageSrc) return openCrop(file);
  const title = mode === "convert" ? `${file.name} to ${op.label}` : `${op.label}: ${file.name}`;
  const t = toast(title);
  try {
    if (mode === "convert") await runConvert(op, file, t);
    else await runTool(op, file, t);
  } catch (err) {
    t.done(`Could not finish: ${err.message}`, { error: true });
  }
}

async function runConvert(op, file, t) {
  const target = op.target;
  const outName = uniqueName(`${baseName(file.name)}.${target === "tar.gz" ? "tar.gz" : target}`);
  const outKind = target === "gif" ? "image" : (kindOfExt(target) || file.kind);
  if (file.imageSrc && ENCODERS[target] && encoderSupported(ENCODERS[target])) {
    t.progress(0.3);
    const blob = await encode(file.imageSrc, ENCODERS[target], (c) => c);
    const url = trackUrl(blob);
    t.progress(1);
    addFile(makeFile({ name: outName, kind: "image", thumb: url, imageSrc: url }));
    t.done(`Saved ${outName}, ${formatSize(blob.size)}. Converted in your browser.`, { download: { url, name: outName } });
    return;
  }
  await animate(t, DURATION[file.kind] || 1000);
  const keepsPicture = outKind === "image" || (file.kind === "video" && target === "gif");
  addFile(makeFile({ name: outName, kind: outKind, thumb: keepsPicture ? file.thumb : null,
    imageSrc: keepsPicture && file.imageSrc ? file.imageSrc : null }));
  t.done(`Saved ${outName}. Simulated here; the app does it with ${engineFor(file.kind, target)}.`);
}

function engineFor(kind, target) {
  if (["audio", "video"].includes(kind) || target === "gif" || target === "mp3") return "ffmpeg";
  if (kind === "pdf") return target === "docx" || target === "odt" ? "pdf2docx" : "PyMuPDF";
  if (["document", "ebook"].includes(kind)) return "pandoc";
  if (["slides", "sheet"].includes(kind)) return "LibreOffice";
  if (kind === "image") return "Pillow";
  return "Python";
}

const TOOL_OUTPUT = {
  "tool:image:compress": [" (compressed)"], "tool:image:resize": [" (resized)"], "tool:image:rotate": [" (rotated)"],
  "tool:image:flip": [" (flipped)"], "tool:image:grayscale": [" (grayscale)"], "tool:image:strip": [" (no metadata)"],
  "tool:image:crop": [" (cropped)"], "tool:video:compress": [" (compressed)", "mp4"], "tool:media:trim": [" (trimmed)"],
  "tool:media:split": [" (parts)", null, "folder"], "tool:video:mute": [" (muted)"], "tool:video:audio": ["", "m4a", "audio"],
  "tool:video:rotate": [" (rotated)"], "tool:video:resize": [" (720p)"], "tool:media:speed": [" (2x)"],
  "tool:audio:compress": [" (compressed)", "mp3"], "tool:audio:normalize": [" (normalized)"],
  "tool:pdf:compress": [" (compressed)"], "tool:pdf:split": [" (split)", null, "folder"],
  "tool:pdf:extract": [" (pages)"], "tool:pdf:remove": [" (edited)"], "tool:pdf:rotate": [" (rotated)"],
  "tool:pdf:images": [" (images)", null, "folder"], "tool:any:zip": ["", "zip", "archive"],
  "tool:archive:extract": ["", null, "folder"],
};
const APP_ASKS = {
  "tool:media:trim": "In the app, Trim asks for start and end times first.",
  "tool:media:split": "In the app, Split asks how many parts.",
  "tool:pdf:extract": "In the app, you type the pages to keep.",
  "tool:pdf:remove": "In the app, you type the pages to remove.",
  "tool:media:speed": "In the app, you pick the speed.",
};

// Canvas versions of the image tools: these run for real.
const IMAGE_TOOLS = {
  "tool:image:compress": { quality: 0.55 },
  "tool:image:resize": { scale: 0.5 },
  "tool:image:rotate": { rotate: true },
  "tool:image:flip": { flip: true },
  "tool:image:grayscale": { filter: "grayscale(1)" },
  "tool:image:strip": {},
};

async function runTool(op, file, t) {
  const [suffix, newExt, outKind] = TOOL_OUTPUT[op.id] || [` (${op.label.toLowerCase()})`];
  const ext = newExt || file.ext;
  if (file.imageSrc && IMAGE_TOOLS[op.id]) {
    const cfg = IMAGE_TOOLS[op.id];
    const outExt = ENCODERS[file.ext] && encoderSupported(ENCODERS[file.ext]) ? file.ext : "png";
    const mime = op.id === "tool:image:compress" && outExt === "png" ? "image/webp" : ENCODERS[outExt];
    const finalExt = mime === "image/webp" && outExt === "png" ? "webp" : outExt;
    const name = uniqueName(`${baseName(file.name)}${suffix}.${finalExt}`);
    t.progress(0.4);
    const blob = await encode(file.imageSrc, mime, (canvas, img) => drawWith(canvas, img, cfg), cfg.quality);
    const url = trackUrl(blob);
    addFile(makeFile({ name, kind: "image", thumb: url, imageSrc: url }));
    t.done(`Saved ${name}, ${formatSize(blob.size)}. Done in your browser.`, { download: { url, name } });
    return;
  }
  await animate(t, DURATION[file.kind] || 1000);
  const name = uniqueName(outKind === "folder" ? `${baseName(file.name)}${suffix}` : `${baseName(file.name)}${suffix}.${ext}`);
  const kind = outKind || file.kind;
  addFile(makeFile({ name, kind, thumb: kind === file.kind ? file.thumb : null }));
  t.done(`Saved ${name}. ${APP_ASKS[op.id] || "Simulated here; the app does it locally."}`);
}

function runAction(op, file) {
  const id = op.id.split(":")[1];
  const t = toast(`${op.label}: ${file.name}`, { progress: false });
  if (id === "float") {
    floatFile(file);
    t.done("Parked on the Float shelf. In the app you can drag it out again later.");
  } else if (id === "path") {
    const path = `/home/you/Metamorph Demo/${file.name}`;
    navigator.clipboard?.writeText(path).then(
      () => t.done(`Copied ${path}`),
      () => t.done(`The app would copy ${path}`),
    );
  } else {
    const text = {
      share: "Sends it to your phone through KDE Connect, Bluetooth or e-mail.",
      copy: "Copied as a file: paste it into any folder or chat app.",
      move: "Opens a folder picker and moves it there.",
      terminal: "Opens a terminal in Metamorph Demo.",
    }[id];
    t.done(`${text} (simulated)`);
  }
}

function floatFile(file) {
  const shelf = $("#shelf");
  const items = $("#shelf-items");
  if (!items.querySelector(`[data-id="${file.id}"]`)) {
    const li = document.createElement("li");
    li.dataset.id = file.id;
    li.title = file.name;
    li.innerHTML = thumbHTML(file);
    items.append(li);
  }
  shelf.hidden = false;
}

// ------------------------------------------------------------------ canvas helpers

const encoderCache = {};
function encoderSupported(mime) {
  if (!(mime in encoderCache)) {
    const c = document.createElement("canvas");
    c.width = c.height = 1;
    encoderCache[mime] = c.toDataURL(mime).startsWith(`data:${mime}`);
  }
  return encoderCache[mime];
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("the image could not be read"));
    img.src = src;
  });
}

function drawWith(canvas, img, cfg) {
  const w = Math.round(img.naturalWidth * (cfg.scale || 1));
  const h = Math.round(img.naturalHeight * (cfg.scale || 1));
  const ctx = canvas.getContext("2d");
  if (cfg.rotate) {
    canvas.width = h; canvas.height = w;
    ctx.translate(h, 0); ctx.rotate(Math.PI / 2);
  } else {
    canvas.width = w; canvas.height = h;
    if (cfg.flip) { ctx.translate(w, 0); ctx.scale(-1, 1); }
  }
  if (cfg.filter) ctx.filter = cfg.filter;
  ctx.drawImage(img, 0, 0, w, h);
}

async function encode(src, mime, draw, quality = 0.9) {
  const img = await loadImage(src);
  const canvas = document.createElement("canvas");
  if (draw.length < 2) { // plain re-encode
    canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (mime === "image/jpeg") { ctx.fillStyle = "white"; ctx.fillRect(0, 0, canvas.width, canvas.height); }
    ctx.drawImage(img, 0, 0);
  } else {
    draw(canvas, img);
  }
  return new Promise((resolve, reject) => canvas.toBlob(
    (b) => (b ? resolve(b) : reject(new Error("the browser cannot encode this format"))), mime, quality));
}

function trackUrl(blob) {
  const url = URL.createObjectURL(blob);
  blobUrls.add(url);
  return url;
}

function formatSize(bytes) {
  return bytes > 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} kB`;
}

// ------------------------------------------------------------------ crop editor

async function openCrop(file) {
  const img = await loadImage(file.imageSrc);
  const wrap = document.createElement("div");
  wrap.className = "crop";
  wrap.innerHTML = `
    <div class="crop__panel" role="dialog" aria-modal="true" aria-labelledby="crop-title">
      <div class="crop__head"><h3 class="crop__title" id="crop-title">Crop ${file.name}</h3><span class="crop__size"></span></div>
      <div class="crop__canvas"><img src="${file.imageSrc}" alt="${file.name}">
        <div class="crop__shade"></div><div class="crop__shade"></div><div class="crop__shade"></div><div class="crop__shade"></div>
        <div class="crop__box" tabindex="0" aria-label="Selection. Arrow keys move it, Shift with arrows moves faster.">
          <span class="crop__handle" data-h="nw"></span><span class="crop__handle" data-h="ne"></span>
          <span class="crop__handle" data-h="sw"></span><span class="crop__handle" data-h="se"></span>
        </div>
      </div>
      <div class="crop__foot">
        <p class="hint">Drag to draw, drag inside to move, drag a corner to resize. <kbd>Enter</kbd> crops.</p>
        <button type="button" class="button button--ghost button--small" data-act="cancel">Cancel</button>
        <button type="button" class="button button--small" data-act="crop">${icon("crop")}<span>Crop</span></button>
      </div>
    </div>`;
  stage.append(wrap);
  const area = $(".crop__canvas", wrap);
  const box = $(".crop__box", wrap);
  const shades = $$(".crop__shade", wrap);
  const sizeLabel = $(".crop__size", wrap);
  const W = img.naturalWidth;
  const H = img.naturalHeight;
  let r = { x0: 0.2, y0: 0.2, x1: 0.8, y1: 0.8 };   // fractions of the image
  const MIN = 0.04;

  function paint() {
    const pct = (v) => `${(v * 100).toFixed(3)}%`;
    Object.assign(box.style, { left: pct(r.x0), top: pct(r.y0), width: pct(r.x1 - r.x0), height: pct(r.y1 - r.y0) });
    Object.assign(shades[0].style, { left: 0, top: 0, right: 0, height: pct(r.y0) });
    Object.assign(shades[1].style, { left: 0, top: pct(r.y1), right: 0, bottom: 0 });
    Object.assign(shades[2].style, { left: 0, top: pct(r.y0), width: pct(r.x0), height: pct(r.y1 - r.y0) });
    Object.assign(shades[3].style, { left: pct(r.x1), top: pct(r.y0), right: 0, height: pct(r.y1 - r.y0) });
    sizeLabel.textContent = `${Math.round((r.x1 - r.x0) * W)} x ${Math.round((r.y1 - r.y0) * H)} px`;
  }
  const clamp = (v, a, b) => Math.min(Math.max(v, a), b);
  function frac(e) {
    const b = area.getBoundingClientRect();
    return { x: clamp((e.clientX - b.left) / b.width, 0, 1), y: clamp((e.clientY - b.top) / b.height, 0, 1) };
  }

  let action = null;
  area.addEventListener("pointerdown", (e) => {
    const p = frac(e);
    const handle = e.target.closest(".crop__handle")?.dataset.h;
    const start = { ...r };
    if (handle) action = { type: "resize", handle, start };
    else if (e.target.closest(".crop__box")) action = { type: "move", p, start };
    else { action = { type: "draw", p }; r = { x0: p.x, y0: p.y, x1: p.x, y1: p.y }; }
    area.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  area.addEventListener("pointermove", (e) => {
    if (!action) return;
    const p = frac(e);
    if (action.type === "move") {
      const w = action.start.x1 - action.start.x0;
      const h = action.start.y1 - action.start.y0;
      const x0 = clamp(action.start.x0 + p.x - action.p.x, 0, 1 - w);
      const y0 = clamp(action.start.y0 + p.y - action.p.y, 0, 1 - h);
      r = { x0, y0, x1: x0 + w, y1: y0 + h };
    } else if (action.type === "draw") {
      r = { x0: Math.min(action.p.x, p.x), y0: Math.min(action.p.y, p.y), x1: Math.max(action.p.x, p.x), y1: Math.max(action.p.y, p.y) };
    } else {
      const s = action.start;
      const h = action.handle;
      r = {
        x0: h.includes("w") ? Math.min(p.x, s.x1 - MIN) : s.x0, x1: h.includes("e") ? Math.max(p.x, s.x0 + MIN) : s.x1,
        y0: h.includes("n") ? Math.min(p.y, s.y1 - MIN) : s.y0, y1: h.includes("s") ? Math.max(p.y, s.y0 + MIN) : s.y1,
      };
    }
    paint();
  });
  area.addEventListener("pointerup", () => {
    if (action?.type === "draw" && (r.x1 - r.x0 < MIN || r.y1 - r.y0 < MIN)) r = { x0: 0.2, y0: 0.2, x1: 0.8, y1: 0.8 };
    action = null;
    paint();
  });

  const previous = document.activeElement;
  function close() { wrap.remove(); previous?.focus?.(); }
  async function apply() {
    close();
    const t = toast(`Crop: ${file.name}`);
    const outExt = ENCODERS[file.ext] && encoderSupported(ENCODERS[file.ext]) ? file.ext : "png";
    const name = uniqueName(`${baseName(file.name)} (cropped).${outExt}`);
    const sx = Math.round(r.x0 * W), sy = Math.round(r.y0 * H);
    const sw = Math.max(1, Math.round((r.x1 - r.x0) * W)), sh = Math.max(1, Math.round((r.y1 - r.y0) * H));
    const blob = await encode(file.imageSrc, ENCODERS[outExt], (canvas, image) => {
      canvas.width = sw; canvas.height = sh;
      canvas.getContext("2d").drawImage(image, sx, sy, sw, sh, 0, 0, sw, sh);
    });
    const url = trackUrl(blob);
    addFile(makeFile({ name, kind: "image", thumb: url, imageSrc: url }));
    t.done(`Saved ${name}, ${sw} x ${sh} px. Cropped in your browser.`, { download: { url, name } });
  }
  wrap.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "cancel") close();
    if (act === "crop") apply();
  });
  wrap.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Enter" && !e.target.closest("button")) { e.preventDefault(); apply(); }
    else if (e.target === box && e.key.startsWith("Arrow")) {
      e.preventDefault();
      const step = e.shiftKey ? 0.05 : 0.01;
      const dx = { ArrowLeft: -step, ArrowRight: step }[e.key] || 0;
      const dy = { ArrowUp: -step, ArrowDown: step }[e.key] || 0;
      const w = r.x1 - r.x0, h = r.y1 - r.y0;
      const x0 = clamp(r.x0 + dx, 0, 1 - w), y0 = clamp(r.y0 + dy, 0, 1 - h);
      r = { x0, y0, x1: x0 + w, y1: y0 + h };
      paint();
    } else if (e.key === "Tab") {
      // keep focus inside the dialog
      const focusables = $$("button, [tabindex='0']", wrap);
      const i = focusables.indexOf(document.activeElement);
      const next = focusables[(i + (e.shiftKey ? -1 : 1) + focusables.length) % focusables.length];
      e.preventDefault();
      next.focus();
    }
  });
  paint();
  box.focus();
}

// ------------------------------------------------------------------ reset, copy, static wheels

function reset() {
  closeWheel();
  $$(".crop").forEach((c) => c.remove());
  blobUrls.forEach((u) => URL.revokeObjectURL(u));
  blobUrls.clear();
  files = initialFiles();
  renderFiles();
  toasts.innerHTML = "";
  $("#shelf-items").innerHTML = "";
  $("#shelf").hidden = true;
  latched = null;
  keyButtons.forEach((k) => k.setAttribute("aria-pressed", "false"));
  restoreHint();
}
$("#reset").addEventListener("click", reset);

$("#copy-install").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  const text = $("#install-commands").innerText.split("\n").map((l) => l.replace(/^\$\s*/, "")).join("\n");
  button.setAttribute("aria-busy", "true");
  try {
    await navigator.clipboard.writeText(text);
    button.classList.add("is-done");
    $(".button__text", button).textContent = "Copied";
  } catch {
    $(".button__text", button).textContent = "Select and copy";
  }
  button.removeAttribute("aria-busy");
  setTimeout(() => { button.classList.remove("is-done"); $(".button__text", button).textContent = "Copy"; }, 2400);
});

function renderStaticWheels() {
  const highlight = { convert: "GIF", tool: "Crop", action: "Float" };
  for (const host of $$("[data-static-wheel]")) {
    const mode = host.dataset.staticWheel;
    const file = makeFile({ name: host.dataset.file });
    const items = opsFor(file, mode);
    const api = createWheel({ items, mode, idPrefix: `static-${mode}`, interactiveLabel: false });
    host.append(api.root);
    const index = items.findIndex((i) => i.label === highlight[mode]);
    if (index >= 0) api.setHot(index);
    host.setAttribute("role", "img");
    host.setAttribute("aria-label", `${MODE_TITLES[mode]} wheel for ${file.name}: ${items.map((i) => i.label).join(", ")}`);
  }
}

// ------------------------------------------------------------------ start

renderIcons();
renderFormats();
renderStaticWheels();
files = initialFiles();
renderFiles();
restoreHint();
if (coarse) $("#window-cue").innerHTML = `${icon("mouse-pointer-2")}Tap Convert, Tools or Actions below, then drag a file`;
})();
