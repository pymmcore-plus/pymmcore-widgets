# Troubleshooting

## No Qt bindings

```sh
qtpy.QtBindingsNotFoundError: No Qt bindings could be found
```

If you get an error similar to the one above, it means that you did not install one of the necessary [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries (for example, you can run `pip install PyQt6` to install [PyQt6](https://pypi.org/project/PyQt6/)).

See the [Installing PyQt or PySide](getting_started.md#installing-pyqt-or-pyside) section for more details.
