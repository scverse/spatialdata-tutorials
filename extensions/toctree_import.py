"""Sphinx extension: import the toctrees of a document of another Sphinx project.

Read the Docs serves related projects on one domain (e.g. the tutorials as the subproject
``/projects/tutorials/`` of the spatialdata docs). To make them one site, each project shows
the other's pages in its sidebar::

    ```{toctree-import} spatialdata
    :source: index.md
    ```

At read time, the directive fetches ``<project>/_sources/<source>.txt`` (the document as the
other project built it; ``:source:`` may also be a full URL) and parses its toctrees
(MyST ``{toctree}`` blocks and reST ``.. toctree::`` directives). It turns them into hidden
toctrees of this project:

- an entry that is a page of the other project becomes a link to it, with its URL and title
  from the project's intersphinx inventory (named by the directive's argument);
- an entry listed in ``toctree_import_local[<project>]`` (other project's docname -> local
  docname) becomes that local document, e.g. the other project's link back to us;
- external links (``Title <https://…>``) stay as they are.

A page missing from the inventory, or a source that can't be fetched or has no toctrees, is a
warning: like an unreachable intersphinx inventory, it fails a ``-W`` build.

The version of the other project is set once, in ``intersphinx_mapping``; the source is read
from the same place as the inventory, so the two match. If the intersphinx target is
root-relative (e.g. ``/en/stable/`` with an absolute inventory URL), the links to the other
project are written root-relative, so they stay on the shared domain.

Meant to move into ``scverse_doc``.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.directives.other import TocTree
from sphinx.ext.intersphinx._shared import InventoryAdapter
from sphinx.util import logging, requests
from sphinx.util.docutils import SphinxDirective

if TYPE_CHECKING:
    from docutils.nodes import Node
    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_EXPLICIT_RE = re.compile(r"^(?P<title>.+?)\s*<(?P<ref>[^<>]+)>$")
_MYST_RE = re.compile(r"^(?P<fence>```+|:::+)\s*\{toctree\}[^\n]*\n(?P<body>.*?)^(?P=fence)\s*$", re.M | re.S)
_REST_RE = re.compile(
    r"^(?P<indent>[ \t]*)\.\. toctree::[^\n]*\n(?P<body>(?:(?P=indent)[ \t]+[^\n]*\n|[ \t]*\n)*)", re.M
)
_OPTION_RE = re.compile(r"^:(?P<name>[\w-]+):\s*(?P<value>.*)$")
_SUFFIXES = (".md", ".ipynb", ".rst", ".txt", ".myst")


def parse_toctrees(text: str) -> list[tuple[str | None, list[str]]]:
    """``(caption, entries)`` of each toctree in a MyST or reST document, in order."""
    blocks = [(m.start(), m["body"]) for m in _MYST_RE.finditer(text)]
    blocks += [(m.start(), m["body"]) for m in _REST_RE.finditer(text)]
    toctrees = []
    for _, body in sorted(blocks):
        caption, entries = None, []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            if option := _OPTION_RE.match(line):
                if option["name"] == "caption":
                    caption = option["value"]
            else:
                entries.append(line)
        toctrees.append((caption, entries))
    return toctrees


def _project(app: Sphinx, name: str) -> tuple[str, str]:
    """The intersphinx target of `name`, and the absolute URL of its root."""
    target, (location, *_) = app.config.intersphinx_mapping[name][1]
    if _URL_RE.match(target):
        return target, target.rstrip("/") + "/"
    if location is None or not _URL_RE.match(location):
        msg = f"intersphinx target {target!r} of {name!r} is relative, so its inventory must be an absolute URL"
        raise ValueError(msg)
    return target, posixpath.dirname(location) + "/"


class TocTreeImport(SphinxDirective):
    """Hidden toctrees with the entries of another project's document; see the module docstring."""

    required_arguments = 1
    option_spec: ClassVar = {"source": directives.unchanged_required}

    def run(self) -> list[Node]:
        name = self.arguments[0]
        source = self.options.get("source", "index.md")
        if name not in self.config.intersphinx_mapping:
            return self._fail(f"{name!r} is not in intersphinx_mapping")
        target, base = _project(self.env.app, name)
        url = source if _URL_RE.match(source) else f"{base}_sources/{source}.txt"
        # the toctrees come from outside: read this document again on every build
        self.env.note_reread()
        try:
            response = requests.get(
                url,
                timeout=self.config.intersphinx_timeout or 30,
                _user_agent=self.config.user_agent,
                _tls_info=(self.config.tls_verify, self.config.tls_cacerts),
            )
            response.raise_for_status()
        except Exception as e:  # noqa: BLE001
            return self._fail(f"couldn't fetch {url}: {e}")
        toctrees = parse_toctrees(response.text)
        if not toctrees:
            return self._fail(f"no toctrees in {url}")

        docs = InventoryAdapter(self.env).named_inventory.get(name, {}).get("std:doc", {})
        local: dict[str, str] = self.config.toctree_import_local.get(name, {})
        source_dir = posixpath.dirname(source) if not _URL_RE.match(source) else ""
        nodes = []
        for caption, entries in toctrees:
            lines = [e for entry in entries if (e := self._entry(entry, docs, local, source_dir, target, base))]
            if lines:
                nodes += self._toctree(caption, lines)
        return nodes

    def _entry(self, entry: str, docs: dict, local: dict[str, str], source_dir: str, target: str, base: str):
        if explicit := _EXPLICIT_RE.match(entry):
            title, ref = explicit["title"], explicit["ref"]
        else:
            title, ref = None, entry
        if _URL_RE.match(ref):
            return entry
        if ref == "self" or "*" in ref:
            return None
        docname = posixpath.normpath(ref[1:] if ref.startswith("/") else posixpath.join(source_dir, ref))
        if docname not in local and docname not in docs and docname.endswith(_SUFFIXES):
            docname = posixpath.splitext(docname)[0]
        if docname in local:
            ref = "/" + local[docname].lstrip("/")
            return f"{title} <{ref}>" if title else ref
        if (item := docs.get(docname)) is None:
            logger.warning(
                "%r (in %s's toctrees) is not in its intersphinx inventory",
                docname,
                self.arguments[0],
                location=self.get_location(),
                type="toctree_import",
            )
            return None
        uri = getattr(item, "uri", None) or item[2]
        display_name = getattr(item, "display_name", None) or item[3]
        # toctree links must be absolute URLs; made root-relative again in `_root_relative`
        if uri.startswith(target):
            uri = base + uri.removeprefix(target)
        return f"{title or display_name} <{uri}>"

    def _toctree(self, caption: str | None, lines: list[str]) -> list[Node]:
        options = {"hidden": None, "maxdepth": 1}
        if caption:
            options["caption"] = caption
        toctree = TocTree(
            "toctree",
            [],
            options,
            StringList(lines, source=self.get_source_info()[0]),
            self.lineno,
            self.content_offset,
            self.block_text,
            self.state,
            self.state_machine,
        )
        return toctree.run()

    def _fail(self, msg: str) -> list[Node]:
        logger.warning("toctree-import: %s", msg, location=self.get_location(), type="toctree_import")
        return []


def _root_relative(app: Sphinx, exception: Exception | None) -> None:
    """Make links to projects with a root-relative intersphinx target root-relative, in the written HTML.

    Toctree entries must be absolute URLs, and pydata-sphinx-theme caches the rendered sidebar,
    so this happens after writing.
    """
    if exception is not None or app.builder.format != "html":
        return
    replacements = []
    for name, (target, _) in app.config.intersphinx_mapping.values():
        if not _URL_RE.match(target):
            replacements.append((f'href="{_project(app, name)[1]}', f'href="{target.rstrip("/")}/'))
    if not replacements:
        return
    for path in Path(app.outdir).rglob("*.html"):
        html = original = path.read_text(encoding="utf-8")
        for old, new in replacements:
            html = html.replace(old, new)
        if html != original:
            path.write_text(html, encoding="utf-8")


def setup(app: Sphinx) -> dict[str, object]:
    app.add_config_value("toctree_import_local", {}, "env", types=frozenset({dict}))
    app.add_directive("toctree-import", TocTreeImport)
    app.connect("build-finished", _root_relative)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
