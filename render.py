"""Tally data -> docs/index.html + docs/style.css. No parsing/aggregation logic here."""

import os
import shutil

from templates.index_template import render as render_html

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def render_site(aggregate_result, generated_at_str, docs_dir):
    os.makedirs(docs_dir, exist_ok=True)

    html_str = render_html(aggregate_result, generated_at_str)
    with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_str)

    shutil.copyfile(
        os.path.join(TEMPLATE_DIR, "style.css"),
        os.path.join(docs_dir, "style.css"),
    )
