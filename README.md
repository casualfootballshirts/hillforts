# Hillforts Map

A static directory of the hillforts of Britain and Ireland for [hillfortsmap.co.uk](https://hillfortsmap.co.uk). Every record comes from the Atlas of Hillforts of Britain and Ireland. Pages show structured facts, a map, and source links. About 300 of the strongest, most visitable records also have a short original introduction written from those facts.

This site is a derivative of the Atlas dataset and is shared under the same licence, **CC BY-SA 4.0**.

## Attribution

Lock & Ralston, Atlas of Hillforts of Britain and Ireland.

- DOI: [https://doi.org/10.5284/1118744](https://doi.org/10.5284/1118744)
- Atlas: [https://hillforts.arch.ox.ac.uk](https://hillforts.arch.ox.ac.uk)
- Licence: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

The same attribution is in the footer of every page. Do not drop it if you republish the data or the text.

## What is published

Structured fields only: names, Atlas number, country, county, parish, coordinates, grid reference, altitude, type, condition, morphology, areas, rampart and entrance counts, dating flags, investigation and entrance categories, HER and NMR identifiers, scheduled monument numbers, bibliography citations, and links.

These narrative columns are not imported and must not be added later, either verbatim or paraphrased:

- Summary Description
- Interior Summary
- Investigations Summary
- Enclosing Works Summary and Enclosing Works comments
- Entrances Summary and entrance comments
- Monument Condition Comments
- Hillfort Type Comments
- Interpretation Comments
- Data Comments
- any other free-text `*Comments` column

The enrichment workbooks (`refs`, `dating`, `entrances`, `investigations`) repeat those comment fields. Their structured values are already on the main table, so the importer reads the main workbook only.

## Indexation

All 4,147 records get a page. About 300 are indexed (`index,follow` and listed in `sitemap.xml`). The rest use `noindex,follow` and stay out of the sitemap until they have a stronger public record.

Ranking prefers extant sites, a Wikipedia article linked from the record’s Wikidata item, a scheduled monument number, a recorded enclosed area, and a short list of well-known names. Home, the six nation hubs, and every current-county hub are indexed.

## Maps

Leaflet with OpenStreetMap tiles and [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster). The home page clusters the full set. Nation and county pages open the same map, already limited to that place. Each site page has a single marker at the Atlas coordinates.

The public OpenStreetMap tile servers are not a guaranteed production host. If traffic grows, point `src/assets/directory.js` at a tile service whose terms allow this use, and keep the OpenStreetMap attribution.

## Rebuild

Import needs Python 3 and `openpyxl`. The site build uses the Python standard library only.

```bash
pip install -r requirements-import.txt
python scripts/import_xlsx.py --main /path/to/main11.xlsx
python scripts/build_site.py
python scripts/verify_site.py
```

`import_xlsx.py` looks up Wikipedia sitelinks on Wikidata (article URLs only, no article text) and writes:

- `data/sites.json` — structured records used by the generator
- `data/wikipedia.json` — QID to article URL cache

Pass `--skip-wikidata` to reuse the cache. Do not commit the raw `.xlsx` files.

The generator writes `dist/`. Open `dist/index.html` through a local web server so the map can load `data/map.json`:

```bash
python -m http.server 8000 --directory dist
```

## GitHub Pages

The site is deployed with GitHub Actions (`.github/workflows/pages.yml`). On every push to `main` the workflow builds `dist/` and deploys it with `actions/deploy-pages`.

After this workflow is on `main`:

1. In the repository, open **Settings → Pages**.
2. Set **Source** to **GitHub Actions**.
3. The custom domain is declared in `CNAME` as `hillfortsmap.co.uk`. Confirm that domain under Pages settings when the first deployment finishes.

### DNS

At the DNS host for `hillfortsmap.co.uk`, point the apex at GitHub Pages. Use all four A records:

- `185.199.108.153`
- `185.199.109.153`
- `185.199.110.153`
- `185.199.111.153`

And the AAAA records:

- `2606:50c0:8000::153`
- `2606:50c0:8001::153`
- `2606:50c0:8002::153`
- `2606:50c0:8003::153`

If the DNS host supports `ALIAS` or `ANAME`, that record can point the apex at `casualfootballshirts.github.io` instead of the A/AAAA set.

For `www.hillfortsmap.co.uk`, add a CNAME record to `casualfootballshirts.github.io`. The Pages domain itself is the apex, which is the name in the `CNAME` file.

GitHub’s own instructions for these addresses are at [Configuring a custom domain for your GitHub Pages site](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site).

## Layout

- `/` — introduction, nation links, clustered map of every site
- `/nations/{nation}/` — Scotland, England, Wales, Republic of Ireland, Northern Ireland, Isle of Man
- `/counties/{county}/` — current county or unitary authority
- `/sites/{atlas-code}-{name}/` — one page per Atlas record
- `/sitemap.xml` — indexed URLs only
- `/robots.txt`
- `/404.html`

Hub filters run in the browser: type, condition, morphology (partial circuits count as univallate, bivallate, or multivallate), scheduled monument number yes/no, and free-text search.

## Third-party map code

Leaflet (BSD 2-Clause) and Leaflet.markercluster (MIT) are vendored in `src/assets/vendor/` with their licence files.
