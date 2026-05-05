# RobinsonAnimator

`RobinsonAnimator` renders animated weather maps using the **Robinson
projection** — a pseudo-cylindrical, compromise projection designed by Arthur
Robinson in 1963 and used by National Geographic from 1988 to 1998.  It is the
go-to choice whenever you need a visually balanced **world or hemispheric map**
that neither stretches the poles nor squashes the tropics.

It shares the same API, dark theme, variable presets, and quality presets as
`PlateCarreeAnimator` and `OrthoAnimator`.

---

## Contents

- [When to use Robinson vs other projections](#when-to-use-robinson-vs-other-projections)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Region definition](#region-definition)
  - [Named shortcuts](#named-shortcuts)
  - [Explicit bounding box](#explicit-bounding-box)
  - [Zoom around a point](#zoom-around-a-point)
  - [central\_longitude](#central_longitude)
- [Output options](#output-options)
- [Quality presets](#quality-presets)
- [Variable presets & colormaps](#variable-presets--colormaps)
- [Title & date](#title--date)
- [Feature flags](#feature-flags)
- [Annotations](#annotations)
- [Author label](#author-label)
- [Full API reference](#full-api-reference)
- [Examples](#examples)

---

## When to use Robinson vs other projections

| Projection | Best for | Avoid when |
|---|---|---|
| **Robinson** | World maps, hemispheres, global thematic weather | You need strict area preservation |
| PlateCarree | Regional flat maps, data grids | Global maps (poles stretched) |
| Orthographic | Single-hemisphere "globe" view, dramatic visuals | Multi-region comparisons |

Robinson is ideal for:
- Global temperature anomaly maps
- World precipitation summaries
- Jet-stream or pressure-system animations spanning multiple continents
- Publication-quality thematic maps

---

## Installation

`RobinsonAnimator` lives in the same package as `OrthoAnimator` and
`PlateCarreeAnimator`.  No additional dependencies are required beyond those
already used by those classes:

```
cartopy
matplotlib
numpy
imageio[ffmpeg]
xarray
```

---

## Quick start

```python
from noaawc.robinson import RobinsonAnimator

anim = RobinsonAnimator(ds, "t2m")
anim.set_region("global")
anim.set_output("world_temperature.mp4")
anim.animate()
```

Static single frame:

```python
anim = RobinsonAnimator(ds, "t2m")
anim.set_region("global")
anim.plot(time_idx=0, save="world_t2m.png", show=False)
```

---

## Region definition

You **must** define the visible region before calling `animate()` or `plot()`.
Three approaches are available; all return `self` for chaining.

### Named shortcuts

```python
anim.set_region("global")           # Full world map (default)
anim.set_region("north_hemisphere") # 0°…85°N
anim.set_region("south_hemisphere") # 85°S…0°
anim.set_region("atlantic")         # North & South Atlantic
anim.set_region("pacific")          # Pacific basin (crosses date-line)
anim.set_region("south_america")    # South American continent
anim.set_region("africa")           # African continent
anim.set_region("europe_asia")      # Eurasia
anim.set_region("north_america")    # North America
anim.set_region("asia")             # Asian continent
```

Each shortcut also sets an appropriate `central_longitude` automatically.

### Explicit bounding box

Pass a dict with the four edge keys.  `central_longitude` is optional
(defaults to `0`):

```python
anim.set_region(
    region={
        "toplat":    75,
        "bottomlat": -60,
        "leftlon":   -180,
        "rightlon":   180,
        "central_longitude": -30,   # rotate projection for Atlantic focus
    }
)
```

Or use keyword arguments:

```python
anim.set_region(
    toplat=75, bottomlat=-60,
    leftlon=-180, rightlon=180,
    central_longitude=-30,
)
```

### Zoom around a point

`set_zoom(zoom, pos)` builds a square bounding box centred on `pos=(lat, lon)`
and sets `central_longitude` to the centre longitude automatically.

```python
anim.set_zoom(zoom=1, pos=(20.0,  0.0))   # Global, Africa-centred
anim.set_zoom(zoom=2, pos=(10.0, 20.0))   # Africa continent
anim.set_zoom(zoom=3, pos=(50.0, 10.0))   # Western Europe
anim.set_zoom(zoom=4, pos=(-9.4, -40.5))  # Northeast Brazil
```

| zoom | Half-side | Typical coverage |
|---|---|---|
| 1 | 90° | Near-global |
| 2 | 45° | Continental |
| 3 | 30° | Sub-continental |
| 4 | 22.5° | Regional |
| 6 | 15° | Country-level |
| 8 | 11.25° | State / province |

### central\_longitude

The Robinson projection has a `central_longitude` parameter that rotates the
entire globe so a chosen meridian appears at the centre of the map.  This
reduces distortion in the area of interest and avoids splitting important
regions across the left/right edges.

Rule of thumb: set `central_longitude` to the average longitude of the region
you care about.

```python
# Africa focused: centre on ~17°E
anim.set_region("africa")               # already sets central_longitude=17.5

# Custom Atlantic view: centre on −30°
anim.set_region(
    toplat=70, bottomlat=-55,
    leftlon=-90, rightlon=30,
    central_longitude=-30,
)
```

---

## Output options

```python
anim.set_output("world_t2m.mp4")    # output file path (.mp4 or .gif)
anim.set_fps(24)                     # frames per second
anim.set_step(2)                     # spatial decimation (1 = none)
anim.set_dpi(120)                    # dots per inch
anim.set_figsize(16.0, 9.0)          # figure size in inches
anim.set_codec("libx264")            # video codec
anim.set_video_quality(8)            # 0–10 (10 = maximum)
```

All setters return `self` and can be chained:

```python
(
    RobinsonAnimator(ds, "prmsl")
    .set_region("global")
    .set_quality("hd")
    .set_output("world_pressure.mp4")
    .animate()
)
```

---

## Quality presets

Apply a named preset with `set_quality()`:

```python
anim.set_quality("sd")      # 1280×720 px @ 6 fps  — fast, small file
anim.set_quality("hd")      # 1920×1080 px @ 24 fps — balanced
anim.set_quality("4k")      # 3840×2160 px @ 30 fps — maximum quality
anim.set_quality("4k_60")   # 3840×2160 px @ 60 fps — silky smooth
```

| Preset | Resolution | FPS | Use case |
|---|---|---|---|
| `sd` | 1280×720 | 6 | Quick preview, social media |
| `hd` | 1920×1080 | 24 | Standard broadcast / YouTube |
| `4k` | 3840×2160 | 30 | High-end publication |
| `4k_60` | 3840×2160 | 60 | Ultra-smooth presentation |

---

## Variable presets & colormaps

Variable presets (colormap, levels, labels) are loaded automatically from
`VARIABLE_PRESETS` when you pass `var` to the constructor.  Available
variables are the same as those supported by `OrthoAnimator` and
`PlateCarreeAnimator` (e.g. `"t2m"`, `"prmsl"`, `"tp"`, `"u10"`, …).

Override any part of the preset:

```python
anim.set_cmap("RdBu_r")
anim.set_levels(np.arange(-30, 31, 2))
anim.set_cbar_label("Temperature anomaly (°C)")
anim.set_plot_title("Global T2m Anomaly")
```

Re-apply the built-in defaults for a variable:

```python
anim.use_variable_defaults("t2m")
```

---

## Title & date

**Static title** (same on every frame):

```python
anim.set_plot_title("Global Temperature — Robinson")
```

**Dynamic title** (date substituted per frame using `%S`):

```python
anim.set_title("Global Surface Temperature — %S", date_style="en")
anim.set_title("Temperatura Global — %S",          date_style="pt-br")
anim.set_title("Temperatura Global — %S",          date_style="es")
anim.set_title("Température mondiale — %S",        date_style="fr")
```

---

## Feature flags

```python
anim.set_states(True)    # show state/province boundaries (default: off)
anim.set_ocean(False)    # hide ocean fill (default: on)
anim.set_grid(False)     # hide lat/lon gridlines (default: on)
```

> **Note on Robinson gridlines:** Cartopy's automatic label placement has
> limited support for the Robinson projection.  Gridlines are drawn without
> labels to avoid rendering artefacts.  For publication maps requiring labelled
> parallels and meridians, draw them manually with `ax.annotate()` after
> obtaining the axes from `_build_axes()`.

---

## Annotations

Add city markers or point-value labels to every frame:

```python
anim.set_annotate("London %.1f°C",    pos=(51.5,  -0.1))
anim.set_annotate("New York %.1f°C",  pos=(40.7, -74.0), color="#58a6ff")
anim.set_annotate("Cairo %.1f°C",     pos=(30.0,  31.2), marker="*")
anim.set_annotate("Equator",          pos=( 0.0,   0.0), interpolate=False)
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `text_base` | — | Label text; `%.1f` is replaced with the interpolated field value if `interpolate=True` |
| `pos` | — | `(lat, lon)` in decimal degrees |
| `size` | `9.0` | Font size (scaled with DPI) |
| `color` | `"#e6edf3"` | Text colour |
| `weight` | `"bold"` | Font weight |
| `alpha` | `0.9` | Text opacity |
| `bbox` | `True` | Draw a rounded background box behind the label |
| `bbox_color` | `"#0d1117"` | Background fill colour |
| `bbox_alpha` | `0.55` | Background opacity |
| `interpolate` | `True` | Bilinearly interpolate the field value at `pos` |
| `zorder` | `5` | Drawing order (higher = on top) |
| `marker` | `"o"` | Matplotlib marker style; `None` to hide |
| `marker_size` | `6.0` | Marker size (scaled with DPI) |
| `marker_color` | same as `color` | Fill colour for the marker |
| `marker_edge_color` | `"#0d1117"` | Marker edge colour |
| `marker_edge_width` | `0.8` | Marker edge width |
| `marker_alpha` | `1.0` | Marker opacity |
| `text_offset` | `(0.0, 0.8)` | `(Δlon, Δlat)` offset of the label from the marker |

Remove all annotations:

```python
anim.clear_annotations()
```

---

## Author label

```python
anim.set_author(
    "Your Name / @handle",
    x=0.50,
    y=0.08,
    color="#e6edf3",
    fontsize=8.5,
    fontweight="bold",
    fontfamily="monospace",
    bbox=True,
    bbox_facecolor="#161b22",
    bbox_edgecolor="#30363d",
    bbox_alpha=0.75,
)
```

Pass `""` to disable the label.

---

## Full API reference

### Constructor

```python
RobinsonAnimator(ds, var)
```

| Parameter | Type | Description |
|---|---|---|
| `ds` | `xarray.Dataset` | GFS dataset loaded by `noaawc` |
| `var` | `str` | Variable name (e.g. `"t2m"`, `"prmsl"`) |

### Region

| Method | Description |
|---|---|
| `set_region(region, ...)` | Named shortcut, dict, or keyword arguments |
| `set_zoom(zoom, pos)` | Square view centred on `pos=(lat, lon)` |

### Output

| Method | Description |
|---|---|
| `set_output(path)` | Output path (`.mp4` or `.gif`) |
| `set_fps(fps)` | Frames per second |
| `set_step(step)` | Spatial decimation factor |
| `set_dpi(dpi)` | Resolution in dots per inch |
| `set_figsize(w, h)` | Figure size in inches |
| `set_codec(codec)` | Video codec (`libx264`, `libx265`, `vp9`, `prores`) |
| `set_video_quality(q)` | Encoding quality 0–10 |
| `set_quality(preset)` | Named quality preset (`"sd"`, `"hd"`, `"4k"`, `"4k_60"`) |

### Colormap

| Method | Description |
|---|---|
| `set_cmap(cmap)` | Colormap name or object |
| `set_levels(levels)` | `BoundaryNorm` levels array |
| `set_cbar_label(label)` | Colorbar label |
| `set_plot_title(title)` | Static frame title |
| `set_title(template, date_style)` | Dynamic title with `%S` date placeholder |
| `use_variable_defaults(var)` | Re-apply built-in preset |

### Feature flags

| Method | Default | Description |
|---|---|---|
| `set_states(visible)` | `False` | State/province boundaries |
| `set_ocean(visible)` | `True` | Ocean fill colour |
| `set_grid(visible)` | `True` | Lat/lon gridlines |

### Annotations & author

| Method | Description |
|---|---|
| `set_annotate(text_base, pos, ...)` | Add a point annotation |
| `clear_annotations()` | Remove all annotations |
| `set_author(name, ...)` | Author/credit label |

### Rendering

| Method | Description |
|---|---|
| `plot(time_idx, save, show)` | Render a single static frame |
| `animate()` | Render all frames and assemble video |

---

## Examples

### Global temperature — quick preview

```python
anim = RobinsonAnimator(ds, "t2m")
anim.set_region("global")
anim.set_quality("sd")
anim.set_output("global_temp_sd.mp4")
anim.animate()
```

### Full-HD world pressure with Atlantic focus

```python
anim = RobinsonAnimator(ds, "prmsl")
anim.set_region(
    toplat=75, bottomlat=-60,
    leftlon=-100, rightlon=40,
    central_longitude=-30,
)
anim.set_quality("hd")
anim.set_title("Mean Sea-Level Pressure — %S")
anim.set_output("atlantic_pressure_hd.mp4")
anim.animate()
```

### Africa precipitation with city markers

```python
anim = RobinsonAnimator(ds, "tp")
anim.set_region("africa")
anim.set_quality("hd")
anim.set_states(True)
anim.set_annotate("Cairo",        pos=(30.0,  31.2), interpolate=False)
anim.set_annotate("Lagos",        pos=( 6.5,   3.4), interpolate=False)
anim.set_annotate("Johannesburg", pos=(-26.2,  28.0), interpolate=False)
anim.set_author("Your Name")
anim.set_output("africa_precip.mp4")
anim.animate()
```

### Single static frame — global view

```python
anim = RobinsonAnimator(ds, "t2m")
anim.set_region("global")
anim.set_dpi(150)
anim.plot(time_idx=0, save="world_t2m_frame0.png", show=False)
```

### Chained fluent API

```python
(
    RobinsonAnimator(ds, "u10")
    .set_region("global")
    .set_quality("4k")
    .set_title("10 m Zonal Wind — %S", date_style="en")
    .set_annotate("Jet Stream Core", pos=(45.0, -30.0), interpolate=False)
    .set_author("Weather Lab / @handle")
    .set_output("global_u10_4k.mp4")
    .animate()
)
```

### Zoom into Western Europe

```python
anim = RobinsonAnimator(ds, "t2m")
anim.set_zoom(zoom=3, pos=(50.0, 10.0))
anim.set_states(True)
anim.set_quality("hd")
anim.set_output("europe_t2m.mp4")
anim.animate()
```

---

## Notes & caveats

**Gridline labels** — Cartopy's automatic label renderer does not fully
support non-cylindrical projections such as Robinson.  Labels are disabled by
default to avoid rendering artefacts.  Gridlines (the lines themselves) are
still drawn.  If you need labelled graticules, add them manually after
retrieving the axes object.

**Poles** — The Robinson projection has finite extent at the poles (unlike
Mercator which goes to ±∞).  Latitudes are clamped to ±85° internally to
avoid edge artefacts in some Cartopy feature datasets.

**Date-line crossing** — For the `"pacific"` preset, `leftlon=100` and
`rightlon=290` cross the date line.  Cartopy handles this correctly when
`central_longitude=180` is set, which the named preset does automatically.

**Aspect ratio** — At global extent the Robinson projection has an intrinsic
~1.97:1 width-to-height ratio.  The 16:9 figsize presets add a small amount
of letterboxing at the top and bottom for global maps, which is normal.

**Performance** — Frame rendering time scales with DPI and region size.  For
global 4K maps, allow ~30–60 seconds per frame on modern hardware.