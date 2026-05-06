ruff format --check noaawc tests test_personality

ruff check noaawc tests test_personality


source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && python -m ruff check . --output-format=github && python -m ruff format --check .

source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && python -m ruff check . --output-format=github && python -m ruff format --check .

source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && pytest tests/ -v -m "not integration" --tb=short --cov=noaawc --cov-report=term-missing --cov-report=xml --junitxml=junit/test-results-local.xml


source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && python -m build && twine check dist/*


 source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && python -m ruff check . --output-format=github && python -m ruff format --check .


source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && python -m mypy noaawc tests test_personality

source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && mypy noaawc/ --ignore-missing-imports

source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && ruff check noaawc/main.py noaawc/projections/api.py noaawc/projections/ortho.py noaawc/projections/plate.py noaawc/projections/robinson.py noaawc/projections/nearside.py --output-format=github


source /home/jezuis/.local/share/virtualenvs/noaawc-X3ScD4Hr/bin/activate && ruff check noaawc/main.py --output-format=github

git status --short --branch


git add CHANGELOG.md noaawc/main.py noaawc/variables.py noaawc/weather.py setup.py tests/test_metadata.py test_personality/gfs_download.py test_personality/make_plots.py test_personality/test_gfs.py test_personality/test_plot_all_keys.py test_personality/test_plot_merc.py test_personality/test_plot_sat.py test_personality/test_video.py test_personality/test_videoplot_all_keys.py noaawc/projections/__init__.py noaawc/projections/api.py noaawc/projections/nearside.py noaawc/projections/ortho.py noaawc/projections/plate.py noaawc/projections/robinson.py


 git commit -m "Release v0.4.1"
git tag -a v0.4.1 -m "v0.4.1"
git push origin main v0.4.1

ruff format --check .

ruff format noaawc/main.py

ruff format --check .