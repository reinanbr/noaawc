from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    readme = fh.read()

setup(
    name="noaawc",
    version="0.5.0",
    url="https://github.com/reinanbr/noaawc",
    license="GPLv3",
    author="Reinan Br",
    author_email="slimchatuba@gmail.com",
    description="Dark-themed animated weather and ocean maps from GFS, GODAS, OISST and ERSST data",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords="climate weather noaa gfs godas oisst ocean plots cartopy",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
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
        "scipy",
        "requests",  # remova se não fizer download direto da NOAA
        "noawclg",
        "kitano",
    ],
)
