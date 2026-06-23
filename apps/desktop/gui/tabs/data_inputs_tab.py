from __future__ import annotations
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from ..widgets.file_picker import FilePicker, PickMode

class DataInputsTab(QWidget):
    _ENTRIES = [('wildland_fire_matrix', 'Wildland Fire Matrix', 'wildland_fire_matrix.mat — known ignition / fire progression → knownig_mat'), ('domain_matrix', 'Domain Matrix', 'domain_matrix.mat — domain classification raster → domains_mat'), ('binary_cover', 'Binary Cover', 'binary_cover_landcover.mat — vegetation vs structure raster → binary_cover'), ('homes_matrix', 'Homes Matrix', 'homes_matrix.mat — building ID raster → homes_mat'), ('latitude', 'Latitude', 'latitude.mat — 1-D latitude vector (length = rows)'), ('longitude', 'Longitude', 'longitude.mat — 1-D longitude vector (length = cols)'), ('radiation_matrix', 'Radiation Matrix', 'radiation_matrix.mat — per-cell radiation hardening → hardening_mat_rad'), ('spotting_matrix', 'Spotting Matrix', 'spotting_matrix.mat — per-cell spotting hardening → hardening_mat_spo'), ('water_matrix', 'Water Matrix', 'water_matrix.mat — non-burnable water cells → water'), ('wind_file', 'Wind File', 'wind.mat — HDF5/v7.3 file containing wind_s and wind_d arrays')]

    def __init__(self, app_dir: str, parent: QWidget | None=None) -> None:
        super().__init__(parent)
        self._app_dir = app_dir
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._pickers: dict[str, FilePicker] = {}
        for key, label, tip in self._ENTRIES:
            lbl = QLabel(label)
            lbl.setToolTip(tip)
            picker = FilePicker(label='', file_filter='MAT files (*.mat)', default_dir=self._app_dir, pick_mode=PickMode.FILE, placeholder=f'Select {label} …')
            picker.setToolTip(tip)
            self._pickers[key] = picker
            form.addRow(lbl, picker)
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)
        reset_btn = QPushButton('Reset to Defaults')
        reset_btn.setFixedWidth(150)
        reset_btn.clicked.connect(self.reset_to_defaults)
        outer.addWidget(reset_btn)

    def get_data_params(self) -> dict:
        params: dict = {'mode': 'extracted'}
        for key, picker in self._pickers.items():
            params[key] = picker.path()
        return params

    def validate(self) -> tuple[bool, str]:
        missing = []
        for key, picker in self._pickers.items():
            p = picker.path()
            if not p or not os.path.isfile(p):
                label = key.replace('_', ' ').title()
                missing.append(label)
        if missing:
            return (False, 'Missing or invalid files:\n• ' + '\n• '.join(missing))
        return (True, '')

    def reset_to_defaults(self) -> None:
        for picker in self._pickers.values():
            picker.set_path('')

    def load_settings(self, data: dict) -> None:
        for key, picker in self._pickers.items():
            if key in data:
                picker.set_path(data[key])
