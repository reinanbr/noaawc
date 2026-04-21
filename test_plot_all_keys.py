from noaawc.variables import VARIABLES_INFO
from noaawc.nearside import NearsidePerspectiveAnimator
from noawclg.main import get_noaa_data as gnd
from kitano import puts
import os
all_keys = list(VARIABLES_INFO.keys())


for key in all_keys:
    puts(f"Processing {key}...")
    try:
        ds = gnd(date="18/04/2026", keys=[key],hours=[0])._ds
        anim = NearsidePerspectiveAnimator(ds, key)
        anim.set_view(lon=-50.0, lat=-15.0)          # centred on Brazil
        anim.set_title(f"{VARIABLES_INFO[key]['long_name']} \n%S", date_style="pt-br")
        anim.set_author('@reinanbr_')
        anim.set_annotate(
            f"Juazeiro - BA: %.1f {VARIABLES_INFO[key]['units']}", pos=(-9.4, -40.5), marker="*",
            marker_color="yellow", marker_size=10, size=6, text_offset=(0.8, 0)
        )
        path_plot = f"./plots/{key}_satellite.png"
        if os.path.exists(path_plot):
            puts(f"Plot for {key} already exists at {path_plot}, skipping...")
            continue
        anim.plot(save=path_plot, show=False)
        puts(f"Saved plot for {key} to {path_plot}")
    except Exception as e:
        write_path = f"./plots/errors/variables_errors.txt"
        with open(write_path, "a") as f:
            f.write(f"Error processing [{key} - {VARIABLES_INFO[key]['long_name']}]:\n{str(e)}\n\n")
        puts(f"Error processing {key}: {e}")
        pass
