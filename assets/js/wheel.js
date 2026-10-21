// The radial wheel, drawn in SVG with the same geometry as the app's wheel.py.

(() => {
const SVG_NS = "http://www.w3.org/2000/svg";
const HUB = 74;
const SINGLE_OUTER = 178;
const MID = 142;
const OUTER = 212;
const INNER_MAX = 8;
const GAP = 3;

const MODE_TITLES = { convert: "Convert", tool: "Tools", action: "Actions" };
const MODE_KEYS = { convert: "Shift", tool: "Alt", action: "Ctrl" };
const MODES = ["convert", "tool", "action"];

function layout(items) {
  const n = items.length;
  if (!n) return [];
  const rings = n <= INNER_MAX + 2
    ? [[HUB, SINGLE_OUTER, items]]
    : [[HUB, MID, items.slice(0, INNER_MAX)], [MID, OUTER, items.slice(INNER_MAX)]];
  const slices = [];
  for (const [r0, r1, ring] of rings) {
    const step = (2 * Math.PI) / ring.length;
    const start = -Math.PI / 2 - step / 2; // first item centred at 12 o'clock
    ring.forEach((item, i) => {
      slices.push({ item, r0, r1, a0: start + i * step, a1: start + (i + 1) * step, index: slices.length });
    });
  }
  return slices;
}

function point(r, a) {
  return [r * Math.cos(a), r * Math.sin(a)];
}

function sectorPath(s) {
  const g1 = GAP / s.r1;
  const g0 = GAP / s.r0;
  const ro = s.r1 - 2;
  const ri = s.r0 + 2;
  const [x1, y1] = point(ro, s.a0 + g1);
  const [x2, y2] = point(ro, s.a1 - g1);
  const [x3, y3] = point(ri, s.a1 - g0);
  const [x4, y4] = point(ri, s.a0 + g0);
  const large = s.a1 - s.a0 > Math.PI ? 1 : 0;
  return `M${x1} ${y1} A${ro} ${ro} 0 ${large} 1 ${x2} ${y2} L${x3} ${y3} A${ri} ${ri} 0 ${large} 0 ${x4} ${y4} Z`;
}

function el(name, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

// Split a hint into at most two short lines for the hub.
function hintLines(text, max = 22) {
  if (text.length <= max) return [text];
  const words = text.split(" ");
  let first = "";
  while (words.length && (first + " " + words[0]).trim().length <= max) first = (first + " " + words.shift()).trim();
  let second = words.join(" ");
  if (second.length > max) second = second.slice(0, max - 1).trimEnd() + "...";
  return [first, second];
}

/**
 * Build a wheel. Returns { root, slices, setHot(index|null), hot(), hitTest(clientX, clientY) }.
 * root is a div.wheel containing the SVG; position it with left/top.
 */
function createWheel({ items, mode, idPrefix = "wheel", interactiveLabel = true, keysHint = true }) {
  const slices = layout(items);
  const outer = slices.length ? Math.max(...slices.map((s) => s.r1)) : SINGLE_OUTER;
  const R = outer + 8;
  const root = document.createElement("div");
  root.className = "wheel";
  const svg = el("svg", { viewBox: `${-R} ${-R} ${2 * R} ${2 * R}`, "aria-hidden": "true" });
  svg.append(el("circle", { class: "wheel__disc", r: R - 2 }), el("circle", { class: "wheel__rim", r: R - 2 }));
  const paths = [];
  const labels = [];
  for (const s of slices) {
    const path = el("path", { class: "wheel__slice", d: sectorPath(s), id: `${idPrefix}-${s.index}` });
    const mid = (s.a0 + s.a1) / 2;
    const [lx, ly] = point((s.r0 + s.r1) / 2, mid);
    const label = el("text", { class: "wheel__label", x: lx.toFixed(1), y: ly.toFixed(1) }, s.item.label);
    if (s.item.label.length > 9) label.classList.add("wheel__label--small");
    paths.push(path);
    labels.push(label);
    svg.append(path, label);
  }
  svg.append(el("circle", { class: "wheel__hub", r: HUB - 3 }));
  const title = el("text", { class: "wheel__mode", x: 0, y: -24 }, MODE_TITLES[mode]);
  const hint1 = el("text", { class: "wheel__hint", x: 0, y: 0 });
  const hint2 = el("text", { class: "wheel__hint", x: 0, y: 15 });
  const keys = el("text", { class: "wheel__keys", x: 0, y: 40 });
  if (keysHint) {
    keys.textContent = MODES.filter((m) => m !== mode).map((m) => `${MODE_KEYS[m]} ${MODE_TITLES[m]}`).join("  ");
  }
  svg.append(title, hint1, hint2, keys);
  root.append(svg);

  let hot = null;
  const idle = slices.length ? "" : "Nothing for this file";
  function setHint(text) {
    const [a, b = ""] = hintLines(text);
    hint1.textContent = a;
    hint2.textContent = b;
  }
  setHint(idle);

  function setHot(index) {
    if (index === hot) return;
    if (hot !== null) {
      paths[hot].classList.remove("is-hot");
      labels[hot].classList.remove("is-hot");
    }
    hot = index;
    if (hot !== null) {
      paths[hot].classList.add("is-hot");
      labels[hot].classList.add("is-hot");
      setHint(slices[hot].item.hint || slices[hot].item.label);
      if (interactiveLabel) root.setAttribute("aria-activedescendant", `${idPrefix}-${hot}`);
    } else {
      setHint(idle);
    }
  }

  function hitTest(clientX, clientY) {
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    const r = Math.hypot(p.x, p.y);
    const a = Math.atan2(p.y, p.x);
    for (const s of slices) {
      if (r < s.r0 || r >= s.r1) continue;
      const rel = (((a - s.a0) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      if (rel < s.a1 - s.a0) return s.index;
    }
    return null;
  }

  return { root, slices, setHot, hot: () => hot, hitTest, setHint };
}

  Object.assign(window.METAMORPH, { createWheel, MODES, MODE_TITLES, MODE_KEYS });
})();
