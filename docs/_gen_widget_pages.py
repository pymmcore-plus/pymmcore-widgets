from pathlib import Path

WIDGETS = Path(__file__).parent / "widgets"


def _widget_list() -> list[str]:
    from qtpy.QtWidgets import QWidget

    import pymmcore_widgets

    widgets = []
    for name in dir(pymmcore_widgets):
        if name.startswith("_"):
            continue
        obj = getattr(pymmcore_widgets, name)
        if isinstance(obj, type) and issubclass(obj, QWidget):
            widgets.append(name)
    return sorted(widgets)


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def generate_widget_pages() -> None:
    """Auto-Generate pages in the widgets folder."""
    from textwrap import dedent

    import mkdocs_gen_files

    for widget in _widget_list():
        if (WIDGETS / f"{widget}.md").exists():
            # skip existing files
            continue

        filename = f"widgets/{widget}.md"
        snake = _camel_to_snake(widget)

        with mkdocs_gen_files.open(filename, "w") as f:
            md = f"""
            ::: pymmcore_widgets.{widget}

            ## Example

            ```python linenums="1" title="{snake}.py"
            --8<-- "examples/{snake}.py"
            ```
            """
            f.write(dedent(md))

        mkdocs_gen_files.set_edit_path(filename, Path(__file__).name)


generate_widget_pages()
