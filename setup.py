from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    readme = fh.read()

setup(
    name="noaawc",
    version="0.3.1",
    url="https://github.com/reinanbr/noaawc",
    license="GPLv3",
    author="Reinan Br",
    author_email="slimchatuba@gmail.com",
    description="Library for plotting dataset from noaa site in basemap",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords="climate weather noaa plots",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "numpy",
        "xarray",
        "matplotlib",
        "cartopy",
        "shapely",
        "cmocean",
        "imageio",
        "imageio-ffmpeg",  # remova se não gerar mp4
        "psutil",
        "pandas",
        "cfgrib",
        "eccodes",
        "netCDF4",
        "requests",  # remova se não fizer download direto da NOAA
        "noawclg",
        "kitano",
    ],
)
