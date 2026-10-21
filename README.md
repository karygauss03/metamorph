# Metamorph website

The product site and interactive demo for [Metamorph](https://github.com/karygauss03/metamorph),
a drag-and-drop file converter for Linux.

**Live:** https://karygauss03.github.io/metamorph-site/

The demo on the page is a small simulated file manager: drag a file, hold
<kbd>Shift</kbd>, <kbd>Alt</kbd> or <kbd>Ctrl</kbd>, and drop it on a slice of the wheel.
On touch screens, tap a key toggle first. Image conversions, the image tools and the crop
editor run for real in the browser; everything else is simulated and labelled as such.

## Layout

```
index.html              the page
assets/css/tokens.css   every colour, size, radius, shadow and duration (the only raw values)
assets/css/site.css     components, mobile first, reads tokens only
assets/js/data.js       wheel contents and format tables, generated from metamorph/registry.py
assets/js/wheel.js      the radial wheel (SVG, same geometry as the app)
assets/js/icons.js      lucide icons used on the page
assets/js/main.js       the interactive demo
```

Plain HTML, CSS and JavaScript: no build step. The scripts are classic deferred scripts, so
the page also works when opened straight from disk.

## Run locally

```sh
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Credits

Icons from [lucide](https://lucide.dev) (ISC). Fonts: Inter and JetBrains Mono (OFL),
served by Google Fonts. Site code under the MIT License.
