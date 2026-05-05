from test_personality.gfs_download import GFSDownloader, plot_nearside

# Download analysis hour for three surface variables
dl = GFSDownloader(date="18/04/2026", cycle="00z", hours=[0])

# Download every variable in VARIABLES_INFO (5-day forecast)
ds = GFSDownloader("18/04/2026").fetch(keys=["v"])

# Skip known-unavailable fields
#ds = GFSDownloader("18/04/2026").fetch(skip=["aptmp"])

# Save and reload
GFSDownloader.save(ds, "gfs_20260418_00z.nc")
ds = GFSDownloader.load("gfs_20260418_00z.nc")

# Plot — Brazil nearside view
plot_nearside(ds, "t2m", central_lon=-50, central_lat=-10, cmap="RdYlBu_r")
