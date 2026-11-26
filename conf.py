# Configuration file for the Sphinx documentation builder.
#
# The tutorials are served as the Read the Docs subproject "tutorials" of the spatialdata docs
# (https://spatialdata.scverse.org/projects/tutorials/), so they share its name, logo, theme and sidebar.
import sys
from pathlib import Path

from scverse_doc.config import DEFAULTS

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "extensions"))

project = "spatialdata"
author = "scverse"
source_repository = "https://github.com/scverse/spatialdata-tutorials"
source_directory = ""

bibtex_bibfiles = ["references.bib"]
templates_path = ["_templates"]

extensions = [
    "scverse_doc",
    "sphinxcontrib.bibtex",
    "IPython.sphinxext.ipython_console_highlighting",
    *[p.stem for p in (HERE / "extensions").glob("*.py")],
]

myst_url_schemes = ("http", "https", "mailto")

intersphinx_mapping = {
    "anndata": ("https://anndata.scverse.org/en/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "geopandas": ("https://geopandas.org/en/stable/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
    "datatree": ("https://datatree.readthedocs.io/en/latest/", None),
    # root-relative: links work on spatialdata.scverse.org, where this project is served
    "spatialdata": ("/en/stable/", "https://spatialdata.scverse.org/en/stable/objects.inv"),
    "spatialdata_plot": ("https://spatialdata.scverse.org/projects/plot/en/latest/", None),
    "spatialdata_io": ("https://spatialdata.scverse.org/projects/io/en/latest/", None),
}

# index.md shows the sidebar of the spatialdata docs ({toctree-import}, extensions/toctree_import.py),
# with its links to the tutorials and datasets pages here pointing to the local pages.
toctree_import_local = {
    "spatialdata": {
        "tutorials/notebooks/notebooks": "notebooks",
        "tutorials/notebooks/datasets/README": "datasets/README",
    },
}

exclude_patterns = [
    *DEFAULTS.exclude_patterns,
    "README.md",  # the repository's README
    "data",
    "temp",
    "notebooks/paper_reproducibility",
    "notebooks/examples/*.zarr",
    "Readme.md",  # hack cause git his acting up
    "notebooks/developers_resources/storage_format/*.ipynb",
    "notebooks/developers_resources/storage_format/Readme.md",
    "notebooks/examples/technology_stereoseq.ipynb",  # no public data available
    "notebooks/examples/technology_curio.ipynb",  # no public data available
    "notebooks/examples/technology_cosmx.ipynb",  # temporarily removed until the new reader and datasets are available
    "notebooks/examples/stereoseq_data/*",
]

html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_logo = "_static/img/spatialdata_horizontal.svg"
html_theme_options = {"show_toc_level": 4}
ogp_image = "_static/img/spatialdata_horizontal.png"
