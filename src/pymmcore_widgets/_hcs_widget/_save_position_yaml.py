# class SavePositions(QDialog):

#     def __init__(self, parent: Optional[QWidget] = None) -> None:
#         super().__init__(parent)


# def _update_plate_yaml(self) -> None:

#         if not self._id.text():
#             return

#         with open(PLATE_DATABASE) as file:
#             f = yaml.safe_load(file)

#         with open(PLATE_DATABASE, "w") as file:
#             new = {
#                 f"{self._id.text()}": {
#                     "circular": self._circular_checkbox.isChecked(),
#                     "id": self._id.text(),
#                     "cols": self._cols.value(),
#                     "rows": self._rows.value(),
#                     "well_size_x": self._well_size_x.value(),
#                     "well_size_y": self._well_size_y.value(),
#                     "well_spacing_x": self._well_spacing_x.value(),
#                     "well_spacing_y": self._well_spacing_y.value(),
#                 }
#             }
#             f.update(new)
#             yaml.dump(f, file)
#             self.yamlUpdated.emit(new)
