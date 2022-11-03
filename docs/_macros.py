from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkdocs_macros.plugin import MacrosPlugin

EXAMPLES = Path(__file__).parent.parent / "examples"
IMAGES = Path(__file__).parent / "_auto_images"
IMAGES.mkdir(exist_ok=True, parents=True)


def define_env(env: MacrosPlugin) -> None:
    """Define the environment for the docs."""

    @env.macro
    def include_example(
        path: str, width: int | None = None, caption: str = "", show_image: bool = True
    ) -> str:
        example = EXAMPLES / path
        src = example.read_text().strip()
        markdown = f"```python\n{src}\n```\n"
        if not show_image:
            return markdown

        image = IMAGES / f"{example.stem}.png"
        if not image.exists():
            _make_image(src, str(image), width)

        if image.exists():
            markdown += dedent(
                f"""
            <figure markdown>
            ![{example.stem}](../../_auto_images/{image.name}){{ width={width} }}
            <figcaption>{caption}</figcaption>
            </figure>
            """
            )

        return markdown


def _make_image(source_code: str, dest: str, width=None):
    """Grab the top widgets of the application."""
    from qtpy.QtWidgets import QApplication

    exec(
        source_code.replace(
            "QApplication([])", "QApplication.instance() or QApplication([])"
        ).replace("app.exec_()", "")
    )

    w = QApplication.topLevelWidgets()[-1]
    w.activateWindow()
    if width:
        w.setFixedWidth(width)
    # w.setMinimumHeight(40)
    w.grab().save(str(dest))
    w.close()
