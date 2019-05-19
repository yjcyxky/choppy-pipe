from __future__ import print_function

from pallets_sphinx_themes import get_version
from pallets_sphinx_themes import ProjectLink

# Project --------------------------------------------------------------

project = "Choppy"
copyright = "2019 Choppy Team"
author = "Choppy Team"
release, version = get_version("choppy")

# General --------------------------------------------------------------

master_doc = "index"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.log_cabinet",
    "pallets_sphinx_themes",
]
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'werkzeug': ('http://werkzeug.pocoo.org/docs/', None),
    'click': ('http://click.pocoo.org/', None),
    'jinja': ('http://jinja.pocoo.org/docs/', None),
    'itsdangerous': ('https://pythonhosted.org/itsdangerous', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/latest/', None),
}

# HTML -----------------------------------------------------------------

html_theme = "flask"
html_theme_options = {"index_sidebar_logo": True}
html_context = {
    "project_links": [
        ProjectLink("Choppy Website", "http://docs.3steps.cn"),
        ProjectLink("Choppy App Store", "http://choppy.3steps.cn"),
        ProjectLink("Source Code", "https://github.com/go-choppy/choppy"),
        ProjectLink("Issue Tracker",
                    "https://github.com/go-choppy/choppy/issues"),
    ]
}
html_sidebars = {
    "index": ["project.html", "localtoc.html", "versions.html", "searchbox.html"],
    "**": ["localtoc.html", "relations.html", "versions.html", "searchbox.html"],
}
singlehtml_sidebars = {
    "index": ["project.html", "versions.html", "localtoc.html"]}
html_static_path = ["_static"]
html_favicon = "_static/choppy-icon.png"
html_logo = "_static/choppy-logo-sidebar.png"
html_title = "Choppy Documentation ({})".format(version)
html_show_sourcelink = False
html_domain_indices = False

# LaTeX ----------------------------------------------------------------

latex_documents = [
    (master_doc, "Choppy-{}.tex".format(version), html_title, author, "manual")
]
latex_use_modindex = False
latex_elements = {
    "papersize": "a4paper",
    "pointsize": "12pt",
    "fontpkg": r"\usepackage{mathpazo}",
    "preamble": r"\usepackage{flaskstyle}",
}
latex_use_parts = True
latex_additional_files = ["flaskstyle.sty", "logo.pdf"]

# Local Extensions -----------------------------------------------------


def github_link(name, rawtext, text, lineno, inliner, options=None, content=None):
    app = inliner.document.settings.env.app
    release = app.config.release
    base_url = "https://github.com/go-choppy/choppy/tree/"

    if text.endswith(">"):
        words, text = text[:-1].rsplit("<", 1)
        words = words.strip()
    else:
        words = None

    if release.endswith("dev"):
        url = "{0}master/{1}".format(base_url, text)
    else:
        url = "{0}{1}/{2}".format(base_url, release, text)

    if words is None:
        words = url

    from docutils.nodes import reference
    from docutils.parsers.rst.roles import set_classes

    options = options or {}
    set_classes(options)
    node = reference(rawtext, words, refuri=url, **options)
    return [node], []


def setup(app):
    app.add_role("gh", github_link)
