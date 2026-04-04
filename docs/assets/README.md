# docs/assets

This directory holds static assets for the GitHub Pages brochure site.

## architecture.png

The architecture diagram is rendered as an **inline SVG** directly inside `docs/index.html`
(see the `<section class="architecture">` element). This keeps the site fully self-contained
with no external dependencies.

If you want to replace it with a raster image, place `architecture.png` here and update
`index.html` to reference `assets/architecture.png` in an `<img>` tag.
