# noaawc

**noaawc** is a Python library for rendering animated and static meteorological maps from GFS (Global Forecast System) data. It provides a high-level API to create publication-quality, dark-themed weather visualizations — orthographic globe maps with smooth camera rotation, per-frame annotations, dynamic titles, and export to MP4 or GIF.

> **noaawc** is built on top of [**noawclg**](https://github.com/your-org/noawclg) — the companion library responsible for downloading, parsing, and organizing GFS GRIB2 data into `xarray.Dataset` objects ready for visualization. You need `noawclg` to obtain the datasets that `noaawc` renders.

---

## Table of Contents

- [How It Fits Together](#how-it-fits-together)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Class: OrthoAnimator](#core-class-orthoanimator)
  - [Constructor](#constructor)
  - [Variable Presets](#variable-presets)
  - [Quality Presets](#quality-presets)
  - [Output Options](#output-options)
  - [Colormap & Levels](#colormap--levels)
  - [Titles & Labels](#titles--labels)
  - [Camera Rotation](#camera-rotation)
  - [Map Annotations](#map-annotations)
  - [Static Snapshot](#static-snapshot)
  - [Rendering the Animation](#rendering-the-animation)
- [Supported Variables](#supported-variables)
  - [Variable Presets Reference](#variable-presets-reference)
  - [VARIABLES\_INFO Reference](#variables_info-reference)
  - [Colormap Design Rationale](#colormap-design-rationale)
  - [Derived Wind Speed Variables](#derived-wind-speed-variables)
- [Utility Functions](#utility-functions)
- [Visual Style](#visual-style)
- [Examples](#examples)
- [Dependencies](#dependencies)

---

## How It Fits Together

noaawc is the **visualization layer** of a two-library pipeline:

```
noawclg  ──────────────────────────────────────────►  noaawc
  │                                                      │
  │  Downloads GFS GRIB2 files from NOAA servers         │  Renders animated / static
  │  Parses variables, levels, and forecast hours        │  orthographic maps from
  │  Converts units (K→°C, Pa→hPa, etc.)                │  xarray Datasets
  │  Returns xarray.Dataset with a time dimension        │
  └──────────────────────────────────────────────────────┘
```

**noawclg** handles everything upstream of the plot: authentication, data download, GRIB2 decoding, unit conversion, and dataset assembly. **noaawc** takes the resulting `xarray.Dataset` and turns it into publication-quality animated or static maps.

### Typical workflow

```python
# Step 1 — download GFS data with noawclg
import noawclg

ds = noawclg.load(
    var="t2m",
    run_date="20260417",
    cycle="00z",
    forecast_hours=range(0, 121, 3),
)

# Step 2 — visualize with noaawc
from noaawc import OrthoAnimator

anim = OrthoAnimator(ds, "t2m")
anim.set_output("temperature.mp4")
anim.animate()
```

> Refer to the [noawclg documentation](https://github.com/your-org/noawclg) for the full download API, available variables, and GFS cycle management.

---

## Features

- 🌍 **Orthographic globe projection** with optional smooth camera rotation across frames
- 🎨 **Dark theme** optimized for social media and presentation use
- 📦 **50+ variable presets** — colormaps, level ranges, and labels auto-loaded for every GFS variable
- 🗃️ **VARIABLES\_INFO metadata** — GRIB2 identifiers, level types, unit converters, and long names for all supported variables
- 🏷️ **Dynamic frame titles** with per-frame timestamps and multi-language month names
- 📍 **Geo-referenced annotations** with configurable markers, labels, and field-value interpolation
- 🖼️ **Per-frame overlays**: info box (variable/cycle/date), data credit, and author label
- 🎬 **MP4 / GIF export** via imageio + ffmpeg, with quality presets from SD to 4K @ 60 fps
- 📸 **Static snapshot** mode for quick single-frame inspection
- ⚡ **Frame caching** — already-rendered PNG frames are reused on re-runs

---

## Installation

```bash
pip install noaawc
```

Install the data companion library as well:

```bash
pip install noawclg
```

**System requirements:**

| Dependency | Purpose |
|---|---|
| `numpy` | Array operations |
| `matplotlib` | Rendering |
| `cartopy` | Map projections and geographic features |
| `cmocean` | Perceptually uniform oceanographic colormaps |
| `imageio[ffmpeg]` | Video encoding |
| `xarray` | GFS dataset interface |

---

## Quick Start

```python
import noawclg
from noaawc import OrthoAnimator

# Download GFS data via noawclg
ds = noawclg.load(var="t2m", run_date="20260417", cycle="00z",
                  forecast_hours=range(0, 121, 3))

# Create animator for 2-metre temperature
anim = OrthoAnimator(ds, "t2m")
anim.set_output("temperature.mp4")

# Optional: add a rotating camera arc
anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
anim.set_rotation_stop(fraction=0.65)

# Render all frames and encode the video
anim.animate()
```

---

## Core Class: OrthoAnimator

### Constructor

```python
OrthoAnimator(ds, var, central_point=(-45.0, -15.0))
```

| Parameter | Type | Description |
|---|---|---|
| `ds` | `xarray.Dataset` | GFS dataset produced by **noawclg**. Must contain the variable `var` with a `time` coordinate. |
| `var` | `str` | Variable key. See [Supported Variables](#supported-variables). |
| `central_point` | `tuple` | Default `(lon, lat)` of the orthographic camera when no rotation is set. |

The constructor automatically loads the matching variable preset (colormap, levels, labels). If no preset exists for `var`, it falls back to temperature defaults and prints a notice.

---

### Variable Presets

All plotting presets are defined in `noaawc.variables` (`presets_extended.py`) inside the `VARIABLE_PRESETS` dictionary. Each entry specifies:

| Field | Description |
|---|---|
| `cmap` | matplotlib colormap object |
| `levels` | 1-D numpy array of BoundaryNorm / contour boundaries |
| `cbar_label` | Colorbar axis label (with units) |
| `plot_title` | Left-side per-frame title |

The active preset is auto-loaded at construction time. To inspect or switch presets:

```python
from noaawc import list_variable_presets
list_variable_presets()   # prints all 50+ presets

# Switch presets after construction
anim.use_variable_defaults("prmsl")     # switch to pressure preset
anim.use_variable_defaults("wspd10")    # switch to 10-m wind speed

# Named convenience shortcuts
anim.use_temperature_defaults()
anim.use_pressure_defaults()
anim.use_precipitation_defaults()
anim.use_humidity_defaults()
anim.use_cloud_water_defaults()
anim.use_wind_speed_defaults()
anim.use_upper_wind_speed_defaults()
```

---

### Quality Presets

Apply a named quality preset that configures DPI, figure size, FPS, codec, and encoding quality in one call:

```python
anim.set_quality("hd")    # Full-HD range, 24 fps
anim.set_quality("4k")    # Ultra HD 4K, 30 fps
anim.set_quality("4k_60") # Ultra HD 4K, 60 fps
anim.set_quality("sd")    # Standard Definition, 6 fps (fast preview)
```

| Preset | DPI | Figure (in) | Output (px) | FPS | Description |
|---|---|---|---|---|---|
| `sd` | 72 | 8 × 8 | 576 × 576 | 6 | Fast preview, small file |
| `hd` | 120 | 10 × 10 | 1200 × 1200 | 24 | Full-HD range (default) |
| `4k` | 220 | 17.07 × 17.07 | ~3755 × 3755 | 30 | Ultra HD 4K |
| `4k_60` | 220 | 17.07 × 17.07 | ~3755 × 3755 | 60 | Ultra HD 4K @ 60 fps |

Print all presets:

```python
from noaawc import list_quality_presets
list_quality_presets()
```

Individual setters override preset values:

```python
anim.set_quality("4k").set_fps(24)   # 4K pixels, cinematic 24 fps
anim.set_dpi(300)                    # print-quality stills
anim.set_figsize(17.07, 17.07)       # custom figure size in inches
anim.set_fps(30)
anim.set_codec("libx265")            # H.265 — ~40% smaller files
anim.set_video_quality(10)           # 0 (worst) – 10 (best)
```

---

### Output Options

```python
anim.set_output("output.mp4")   # MP4 (default) or GIF
anim.set_fps(24)
anim.set_step(2)                # spatial decimation — 1 = full resolution
anim.set_codec("libx264")       # "libx264", "libx265", "vp9", "prores"
anim.set_video_quality(8)       # 0–10; higher = larger file, sharper detail
```

---

### Colormap & Levels

Override the preset colormap and/or level boundaries:

```python
import numpy as np
import cmocean

anim.set_cmap(cmocean.cm.thermal)            # cmocean colormap object
anim.set_cmap("RdBu_r")                      # any matplotlib name string
anim.set_levels(np.arange(960, 1040, 2))     # pressure levels
anim.set_levels(np.linspace(-30, 45, 40))    # custom temperature range
anim.set_cbar_label("Temperature (°C)")
anim.set_plot_title("Surface Temperature")
```

---

### Titles & Labels

#### Dynamic title with per-frame date

Use `%S` as a placeholder — it is replaced with the frame's timestamp:

```python
anim.set_title("Surface Temperature  %S")
# renders as: "Surface Temperature  17 Apr 2026 03:00"

anim.set_title("Temperatura da Superfície — %S", date_style="pt-br")
# renders as: "Temperatura da Superfície — 17 Abr 2026 03:00"
```

Supported `date_style` values:

| Key | Month example | Full example |
|---|---|---|
| `"en"` (default) | Apr | 17 Apr 2026 03:00 |
| `"pt-br"` | Abr | 17 Abr 2026 03:00 |
| `"es"` | Abr | 17 Abr 2026 03:00 |
| `"fr"` | Avr | 17 Avr 2026 03:00 |

#### Author label

```python
anim.set_author("Maria Silva")      # centred at bottom, white bold
anim.set_author("@msilva_met")
anim.set_author("")                 # disable
```

#### Automatic overlays

Every frame includes:

- **Top-right info box** — variable key, long name (pulled from `VARIABLES_INFO`), GFS cycle, and frame date
- **Bottom-right credit** — `GFS 0.25° / NASA · NOAA`

These are always rendered and require no configuration.

---

### Camera Rotation

Define a smooth arc from a start position to an end position:

```python
anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
```

Optionally freeze the camera at the end position after a fraction of the total frames:

```python
anim.set_rotation_stop(fraction=0.65)  # stop rotating at 65% of frames
anim.set_rotation_stop(frame=40)       # stop at absolute frame index 40
```

If `set_rotation` is not called, the camera stays fixed at `central_point`.

---

### Map Annotations

Add geo-referenced city or point labels with optional markers. Use `%d`, `%.1f`, `%.2f`, etc. as a placeholder for the field value sampled at the annotation position.

```python
# Basic: circle marker + temperature value
anim.set_annotate("Juazeiro: %.1f°C", pos=(-9.4, -40.5))

# Custom marker, colour, and text offset
anim.set_annotate(
    "Fortaleza: %.1f°C",
    pos=(-3.72, -38.54),
    marker="*",
    marker_size=10,
    marker_color="#f7c948",
    color="#58a6ff",
    text_offset=(0.5, 1.2),
)

# No marker — text only
anim.set_annotate("Manaus", pos=(-3.10, -60.02), marker=None)

# Method chaining — multiple cities
(anim
    .set_annotate("Recife %.1f m/s",    pos=(-8.05,  -34.88))
    .set_annotate("Fortaleza %.1f m/s", pos=(-3.72,  -38.54))
    .set_annotate("Manaus %.1f m/s",    pos=(-3.10,  -60.02))
)

# Remove all annotations
anim.clear_annotations()
```

**`set_annotate` parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text_base` | `str` | — | Label text. Use `%d`/`%.1f`/`%.2f` for field value. |
| `pos` | `(lat, lon)` | — | Geographic position in decimal degrees. |
| `size` | `float` | `9.0` | Font size in points (at HD 120 dpi). |
| `color` | `str` | `"#e6edf3"` | Text colour. |
| `weight` | `str` | `"bold"` | Font weight: `"normal"`, `"bold"`, `"heavy"`. |
| `alpha` | `float` | `0.9` | Text opacity. |
| `bbox` | `bool` | `True` | Draw a rounded background box. |
| `bbox_color` | `str` | `"#0d1117"` | Background box fill colour. |
| `bbox_alpha` | `float` | `0.55` | Background box opacity. |
| `interpolate` | `bool` | `True` | Replace `%…` placeholder with field value at `pos`. |
| `marker` | `str \| None` | `"o"` | Marker symbol. `None` disables the marker. Common: `"o"`, `"^"`, `"s"`, `"D"`, `"*"`, `"+"`, `"x"`. |
| `marker_size` | `float` | `6.0` | Marker size in points. |
| `marker_color` | `str \| None` | `None` | Marker fill. `None` inherits `color`. |
| `marker_edge_color` | `str` | `"#0d1117"` | Marker outline colour. |
| `marker_edge_width` | `float` | `0.8` | Marker outline width in points. |
| `marker_alpha` | `float` | `1.0` | Marker opacity. |
| `text_offset` | `(Δlon, Δlat)` | `(0.0, 0.8)` | Shift label relative to `pos` in decimal degrees. |

---

### Static Snapshot

Render a single frame without producing a video:

```python
# Open an interactive window
anim.plot(time_idx=0)

# Save to file
anim.plot(time_idx=6, save="snapshot.png")

# Override camera position for this plot only
anim.plot(time_idx=0, central_point=(-60.0, -20.0), save="fig.png")
```

---

### Rendering the Animation

```python
anim.animate()
```

**What `animate()` does:**

1. Creates a `frames/<var>_<run_date>_<cycle>/` directory
2. Renders each time step as a PNG to disk (skipping frames that already exist)
3. Encodes all frames into the output video file

A summary line is printed before the loop:

```
Render: 65 frames  |  1200×1200 px  |  120 dpi  |  24 fps  |  codec=libx264  quality=8  annotations=2  →  output.mp4
```

---

## Supported Variables

All supported variables are registered in **`VARIABLE_PRESETS`** (plotting configuration) and **`VARIABLES_INFO`** (metadata and GRIB2 identifiers), both defined in `noaawc/variables.py`.

---

### Variable Presets Reference

#### Surface temperature & dewpoint

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `t2m` | 2-metre temperature | `cmocean.thermal` | −20 to 50 °C, step 2 |
| `d2m` | 2-metre dewpoint temperature | `cmocean.haline` | −30 to 30 °C, step 2 |
| `aptmp` | Apparent temperature (heat index / wind chill) | `cmocean.thermal` | −30 to 50 °C, step 2 |

#### Humidity

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `r2` | 2-metre relative humidity | `cmocean.haline` | 0–100 %, step 5 |
| `sh2` | 2-metre specific humidity | `cmocean.haline` | 0–26 × 10⁻³ kg kg⁻¹ |
| `pwat` | Precipitable water | `cmocean.haline` | 0–80 kg m⁻², step 4 |
| `cwat` | Column cloud water | `cmocean.ice` | 0–5 kg m⁻² (log-spaced) |

#### 10-metre wind

| Key | Description | Colormap | Level range | Notes |
|---|---|---|---|---|
| `u10` | 10-m U wind component | `RdBu_r` | ±30 m s⁻¹, step 2 | Diverging |
| `v10` | 10-m V wind component | `RdBu_r` | ±30 m s⁻¹, step 2 | Diverging |
| `wspd10` | 10-m wind speed scalar | `cmocean.speed` | 0–30 m s⁻¹, step 1 | **Derived** — see below |
| `gust` | Surface wind gust | `cmocean.speed` | 0–50 m s⁻¹, step 2 | |

#### Pressure

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `prmsl` | Mean sea-level pressure | `RdBu_r` | 960–1044 hPa, step 2 |
| `mslet` | MSLP (Eta model reduction) | `RdBu_r` | 960–1044 hPa, step 2 |
| `sp` | Surface pressure | `RdBu_r` | 500–1050 hPa, step 10 |

#### Precipitation & hydrology

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `prate` | Precipitation rate | `cmocean.rain` | 0–64 mm h⁻¹ (log-spaced) |
| `cpofp` | Frozen precipitation fraction | `cool` | 0–100 %, step 10 |
| `crain` | Categorical rain | `Blues` | 0/1 binary |
| `csnow` | Categorical snow | `winter` | 0/1 binary |
| `cfrzr` | Categorical freezing rain | `PuBu` | 0/1 binary |
| `cicep` | Categorical ice pellets | `Purples` | 0/1 binary |
| `sde` | Snow depth | `cmocean.ice` | 0–2 m (log-spaced) |
| `sdwe` | Snow water equivalent | `cmocean.ice` | 0–500 kg m⁻² |

#### Cloud cover

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `tcc` | Total cloud cover | `cmocean.ice` | 0–100 %, step 5 |
| `lcc` | Low cloud cover | `cmocean.ice` | 0–100 %, step 5 |
| `mcc` | Medium cloud cover | `cmocean.ice` | 0–100 %, step 5 |
| `hcc` | High cloud cover | `cmocean.ice` | 0–100 %, step 5 |

#### Convection & instability

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `cape` | CAPE | `YlOrRd` | 0–5000 J kg⁻¹ (log-spaced) |
| `cin` | Convective inhibition | `RdPu` | −500 to 0 J kg⁻¹ |
| `lftx` | Surface lifted index | `RdBu_r` | −12 to 10 K, step 1 |
| `lftx4` | Best (4-layer) lifted index | `RdBu_r` | −12 to 10 K, step 1 |
| `hlcy` | Storm relative helicity | `YlOrRd` | 0–1000 m² s⁻² |

#### Upper-air / isobaric

| Key | Description | Colormap | Level range | Notes |
|---|---|---|---|---|
| `t` | Temperature | `cmocean.thermal` | −80 to 40 °C, step 4 | Multi-level |
| `r` | Relative humidity | `cmocean.haline` | 0–100 %, step 5 | Multi-level |
| `q` | Specific humidity | `cmocean.haline` | 0–18 × 10⁻³ kg kg⁻¹ | Multi-level |
| `gh` | Geopotential height | `cmocean.deep` | 0–6000 gpm, step 60 | Multi-level |
| `u` | U wind component | `RdBu_r` | ±60 m s⁻¹, step 4 | Multi-level |
| `v` | V wind component | `RdBu_r` | ±60 m s⁻¹, step 4 | Multi-level |
| `w` | Vertical velocity ω | `RdBu_r` | ±5 Pa s⁻¹ (non-uniform) | Multi-level; negative = rising |
| `absv` | Absolute vorticity | `RdBu_r` | ±8 × 10⁻⁴ s⁻¹ | Multi-level |
| `wspd` | Wind speed scalar | `cmocean.speed` | 0–80 m s⁻¹, step 4 | **Derived**, multi-level |

#### Soil (4-layer)

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `st` | Soil temperature | `cmocean.matter` | −10 to 40 °C, step 2 |
| `soilw` | Volumetric soil moisture | `cmocean.matter` | 0–1 (proportion) |

#### Diagnostics & other

| Key | Description | Colormap | Level range |
|---|---|---|---|
| `refc` | Composite radar reflectivity | NWS 18-colour | −10 to 75 dBZ, step 5 |
| `siconc` | Sea ice area fraction | `cmocean.ice` | 0–1 |
| `orog` | Orography / terrain height | `cmocean.topo` | 0–6000 m (non-uniform) |
| `lsm` | Land-sea mask | `BrBG` | 0–1 |
| `veg` | Vegetation fraction | `cmocean.algae` | 0–100 %, step 5 |
| `vis` | Surface visibility | `cmocean.gray` | 0–50 000 m (log-spaced) |
| `tozne` | Total ozone column | `cmocean.deep` | 200–500 DU, step 10 |

---

### VARIABLES\_INFO Reference

`VARIABLES_INFO` is a dictionary exported from `noaawc.variables` that maps every variable key to its full metadata record. It is used internally by `OrthoAnimator` (e.g. to populate the info-box long name) and can be queried directly:

```python
from noaawc.variables import VARIABLES_INFO

info = VARIABLES_INFO["t2m"]
# {
#   "short":      "t2m",
#   "long_name":  "2 metre temperature",
#   "units":      "C",
#   "tlev":       "heightAboveGround",
#   "levels":     [2],
#   "grib_var":   "var_TMP",
#   "grib_lev":   "lev_2_m_above_ground",
#   "converter":  <lambda x: x - 273.15>,
# }
```

Each record contains:

| Field | Type | Description |
|---|---|---|
| `short` | `str` | Short variable key (same as the dictionary key) |
| `long_name` | `str` | Human-readable name shown in the info box overlay |
| `units` | `str` | Physical units of the variable as stored in the dataset |
| `tlev` | `str` | GRIB2 type-of-level string (e.g. `"heightAboveGround"`, `"isobaricInhPa"`) |
| `levels` | `list \| None` | Level values (e.g. `[2]` for 2 m, `[500]` for 500 hPa), or `None` for single-level fields |
| `grib_var` | `str` | GRIB2 variable name used by **noawclg** for filtering |
| `grib_lev` | `str` | GRIB2 level name used by **noawclg** for filtering |
| `converter` | `callable \| None` | Lambda applied by **noawclg** to convert raw SI values (e.g. K → °C, Pa → hPa). `None` = no conversion. |
| `multilevel` | `bool` | `True` for variables that exist at multiple pressure or depth levels |

The `grib_var` and `grib_lev` fields are the primary bridge between `VARIABLES_INFO` and **noawclg** — they are the exact filter strings noawclg uses when selecting messages from GFS GRIB2 files.

---

### Colormap Design Rationale

Colormaps in `VARIABLE_PRESETS` were selected following perceptual and meteorological conventions:

| Variable group | Colormap | Rationale |
|---|---|---|
| Temperature | `cmocean.thermal` | Perceptually uniform; warm palette matches intuition |
| Dewpoint / humidity | `cmocean.haline` | Blue-green tones; intuitive for moisture |
| Wind components (U/V) | `RdBu_r` | Diverging ± around zero; zero centred |
| Wind speed / gust | `cmocean.speed` | Sequential white → dark teal; calm = white |
| Pressure (MSLP/SP) | `RdBu_r` | Diverging: blue = low pressure, red = high |
| Precipitation | `cmocean.rain` | White → navy; log-spaced levels |
| Cloud / water / snow | `cmocean.ice` | White → dark; dense cloud = darker |
| Soil | `cmocean.matter` | Earth brown tones |
| CAPE | `YlOrRd` | Yellow → red instability scale |
| CIN / Lifted Index | `RdPu` / `RdBu_r` | Stable → unstable gradient |
| Vorticity / omega | `RdBu_r` | Diverging ± around zero |
| Categorical fields | `Blues` / `winter` / `PuBu` | Two-tone binary (0 = no, 1 = yes) |
| Reflectivity | NWS 18-colour | Standard WSR-88D radar palette |
| Ozone / geopotential | `cmocean.deep` | Sequential deep-ocean repurposed |

The NWS radar reflectivity palette (`_REFC_CMAP`) is an 18-colour `ListedColormap` matching the standard WSR-88D colour scale used by US National Weather Service products.

---

### Derived Wind Speed Variables

`wspd10` (surface) and `wspd` (upper-air) do not exist directly in GFS GRIB2 files. Compute and attach them to the dataset before creating the animator:

```python
import numpy as np

# 10-m wind speed
ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)

# Upper-air wind speed (isobaric levels)
ds["wspd"] = np.sqrt(ds["u"] ** 2 + ds["v"] ** 2)

anim = OrthoAnimator(ds, "wspd10")
```

For tropical cyclone applications, extend the `wspd10` levels to cover higher wind speeds:

```python
anim.set_levels(np.arange(0, 65, 2))   # up to 64 m/s (Category 5+)
```

---

## Utility Functions

```python
from noaawc import list_variable_presets, list_quality_presets

# Print all variable presets: key, colormap, level range, label
list_variable_presets()

# Print all quality presets: DPI, figure size, FPS, codec, description
list_quality_presets()
```

---

## Visual Style

noaawc uses a consistent dark GitHub-inspired theme across all renders:

| Element | Colour |
|---|---|
| Figure / axes background | `#0d1117` |
| Land fill | `#1c2128` |
| Coastlines | `#58a6ff` |
| Country borders | `#484f58` (dashed) |
| Grid lines | `#21262d` |
| Text (titles, labels) | `#e6edf3` |
| Subtitle / tick text | `#8b949e` |
| Info box background | `#161b22` |
| Info box border | `#30363d` |
| Font family | Monospace |

---

## Examples

### 4K temperature animation with author credit

```python
anim = OrthoAnimator(ds, "t2m")
anim.set_output("temperature_4k.mp4")
anim.set_quality("4k")
anim.set_title("Temperatura 2m — %S", date_style="pt-br")
anim.set_author("Maria Silva")
anim.set_rotation(lon_start=-90, lon_end=-30, lat_start=-10, lat_end=-15)
anim.set_rotation_stop(fraction=0.7)
anim.set_annotate("Juazeiro %.1f°C", pos=(-9.4, -40.5))
anim.set_annotate("Fortaleza %.1f°C", pos=(-3.72, -38.54), color="#58a6ff")
anim.animate()
```

### 10-m wind speed with derived variable

```python
import numpy as np

ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)

anim = OrthoAnimator(ds, "wspd10")
anim.set_output("wind_speed_10m.mp4")
anim.set_title("Wind Speed (10 m)  %S")
anim.set_quality("hd")
anim.animate()
```

### Static snapshot for quick inspection

```python
anim = OrthoAnimator(ds, "prmsl")
anim.plot(time_idx=0, save="mslp_t0.png")
```

### Custom colormap and levels

```python
anim = OrthoAnimator(ds, "cape")
anim.set_cmap("YlOrRd")
anim.set_levels(np.arange(0, 4000, 200))
anim.set_cbar_label("CAPE (J kg⁻¹)")
anim.set_title("CAPE — %S")
anim.set_output("cape.mp4")
anim.animate()
```

### Full method chaining

```python
(OrthoAnimator(ds, "t2m")
    .set_output("t2m_full.mp4")
    .set_quality("4k")
    .set_title("2m Temperature — %S", date_style="en")
    .set_author("INMET / FUNCEME")
    .set_rotation(lon_start=-80, lon_end=-35, lat_start=5, lat_end=-20)
    .set_rotation_stop(fraction=0.6)
    .set_annotate("Recife %.1f°C",    pos=(-8.05,  -34.88))
    .set_annotate("Manaus %.1f°C",    pos=(-3.10,  -60.02))
    .set_annotate("Brasília %.1f°C",  pos=(-15.78, -47.93))
    .animate()
)
```

---

## Dependencies

| Package | Minimum version | Notes |
|---|---|---|
| `noawclg` | latest | GFS data download and parsing — required upstream library |
| `numpy` | ≥ 1.24 | |
| `matplotlib` | ≥ 3.7 | |
| `cartopy` | ≥ 0.22 | Requires GEOS and PROJ system libraries |
| `cmocean` | ≥ 3.0 | |
| `imageio` | ≥ 2.28 | |
| `imageio[ffmpeg]` | — | Required for MP4 output |
| `xarray` | ≥ 2023.1 | |

---

## License

See `LICENSE` for details.

---

## Data Sources

GFS data is provided by **NOAA** (National Oceanic and Atmospheric Administration) at 0.25° horizontal resolution, downloaded and parsed by **noawclg**. Terrain and geographic features are sourced from **Natural Earth** via Cartopy.