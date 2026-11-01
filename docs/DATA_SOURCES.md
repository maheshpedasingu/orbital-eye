# Data sources

## NASA FIRMS (fire / thermal anomalies) - REAL_EXTERNAL

- Access: free MAP_KEY requested from the FIRMS site; stored in `.env` as `FIRMS_MAP_KEY`.
- Used: area CSV for a bounding box (AOI plus 0.5 degree margin), VIIRS_SNPP_NRT, 2-day range.
- Verified from the official API page: key required; box as west,south,east,north;
  day range 1 to 10; NRT sources include VIIRS and MODIS; a data-availability endpoint exists.
- Verified by a live call: the area URL pattern works; the CSV header is
  `latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight`.
- Time: `acq_date` + `acq_time` (HHMM), UTC. VIIRS `confidence` is a letter (l/n/h); stored raw.
- NOT verified: exact rate limits. Check your own usage on the FIRMS site.
- Limits: a detection is a satellite-reported thermal anomaly, not a confirmed fire.
  VIIRS I-band pixels are about 375 m. Near-real-time data arrives within hours of the overpass.
  Many detections in this region may be agricultural burning; no land-cover context is used yet.
- Provenance stored per row: source, retrieval time, ingestion run id, `data_origin`.

## Sentinel-2 L2A via Earth Search (Element 84, AWS) - REAL_EXTERNAL

- Access: public STAC API and Cloud-Optimized GeoTIFFs; no key needed. Free service with no
  guaranteed availability, so the app records failures and never substitutes data.
- Used: collection `sentinel-2-c1-l2a`, tile 44QMD, assets `red` (B04), `nir` (B08), `scl`.
- Verified from live item metadata: red and NIR have scale 0.0001 and offset -0.1,
  nodata 0; SCL has nodata 0. The code reads scale and offset from the item and refuses to
  run without them.
- Resolution: 10 m for B04/B08, 20 m for SCL (resampled to the band grid).
- Credit (required by the Copernicus legal notice for modified data):
  "Contains modified Copernicus Sentinel data [Year]". Shown on the map.
- Limits: scene-level cloud cover describes the whole tile, not the AOI. We use the SCL layer
  inside the AOI instead, and mask cloud, shadow, thin cirrus, saturated and no-data pixels.

## OpenStreetMap tiles (map background)

- Attribution "(c) OpenStreetMap contributors" is displayed. Review the OSM tile usage policy
  before any public deployment; a development laptop is light use only.

## Test fixtures (not real operational data)

- TLE for the ISS from the python-sgp4 documentation, epoch December 2019. Used for tests and
  for the demo orbit view. It does not describe any satellite's current orbit.
- Area of interest: approximate box around 16.506 N, 80.648 E (about 33 km wide). Not a
  surveyed boundary. Edit `config/aoi_vijayawada.geojson` to change it.

## Not yet used

NASA Earthdata products, MODIS imagery, CelesTrak TLEs, and Copernicus Data Space.
## CelesTrak GP data (orbital elements) - REAL_EXTERNAL

- Access: public HTTPS endpoint `https://celestrak.org/NORAD/elements/gp.php?CATNR=<n>&FORMAT=3LE`.
  No key. We always send FORMAT explicitly: two CelesTrak pages disagree about the default
  (TLE on one, CSV on another updated June 2026).
- Used: Suomi NPP (37849) and Sentinel-2B (42063); the returned names matched on the first live fetch.
- Policy: CelesTrak publishes a usage policy; the exact limits were NOT verified here. We fetch each
  satellite at most once per 12 hours (failed attempts count) and store results in SQLite.
- Limits: TLE format cannot carry 6-digit catalogue numbers (100000 and above); a TLE is only accurate
  near its epoch. We refuse to predict from an element set older than 14 days.
- A position computed from a TLE is a PREDICTION, labelled PROPAGATED_FROM_REAL_TLE.

## Instrument swaths used for opportunity prediction

- Sentinel-2 MSI: 290 km (several sources, including a NASA/UMD presentation). Half-swath 145 km.
- VIIRS on Suomi NPP: about 3040 km (SSEC, NASA PO.DAAC GHRSST page) or 3060 km (Wikipedia, PO.DAAC).
  We use a half-swath of 1520 km.
- Local overpass times: Suomi NPP ascending node about 13:30 (SSEC). Sentinel-2 about 10:30 is an
  unverified expectation.
