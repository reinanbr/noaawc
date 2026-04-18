from setuptools import find_packages, setup


with open("README.md", "r") as fh:
    readme = fh.read()

setup(name='noaawc',
    version='0.3.0',
    url='https://github.com/reinanbr/noaawc',
    license='GPLv3',
    author='Reinan Br',
    long_description=readme,
    long_description_content_type="text/markdown",
    author_email='slimchatuba@gmail.com',
    keywords='climate weather noaa plots',
    description=u'Library for plotting dataset from noaa site in basemap',
    packages=find_packages(),
    install_requires=['pygrib','kitano','numpy','noawclg','matplotlib','pandas','cartopy','psutil','imageio','xarray'],)
