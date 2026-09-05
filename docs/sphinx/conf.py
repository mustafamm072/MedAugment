"""Build the existing Markdown guides without maintaining duplicate copies."""
from importlib.metadata import version as package_version

project = "MedAugmentX"
author = "MedAugmentX Contributors"
release = package_version("medaugmentx")
extensions = ["myst_parser"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "docs/sphinx/index"
include_patterns = [
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
    "docs/*.md", "docs/sphinx/index.rst", "examples/README.md", "benchmarks/README.md",
    "notebooks/README.md",
]
myst_heading_anchors = 4
html_theme = "alabaster"
html_title = f"MedAugmentX {release}"
html_show_sourcelink = False
