from __future__ import annotations
import math
from datetime import datetime
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from ..widgets.param_row import ParamRow, ParamType
_T_STEP_MIN: float = 5.0
_T_START = datetime(2025, 1, 7, 18, 20)
_T_END = datetime(2025, 1, 8, 14, 20)

def _calc_steps(t_start: datetime, t_end: datetime) -> int:
    delta_min = (t_end - t_start).total_seconds() / 60.0
    if delta_min <= 0:
        return 0
    return int(delta_min / _T_STEP_MIN) + 1

class GridTimeTab(QWidget):

    def __init__(self, parent: QWidget | None=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self._t_start = ParamRow('Simulation Start', ParamType.DATETIME, default=_T_START, tooltip='Date and time when the simulation begins.')
        self._t_end = ParamRow('Simulation End', ParamType.DATETIME, default=_T_END, tooltip='Date and time when the simulation ends.')
        self._steps_label = QLabel()
        self._steps_label.setStyleSheet('color: #555; font-style: italic;')
        self._update_steps_label()
        self._t_start.value_changed.connect(self._update_steps_label)
        self._t_end.value_changed.connect(self._update_steps_label)
        for row in (self._t_start, self._t_end):
            layout.addWidget(row)
        layout.addWidget(self._steps_label)
        layout.addStretch()
        reset_btn = QPushButton('Reset to Defaults')
        reset_btn.setFixedWidth(150)
        reset_btn.clicked.connect(self.reset_to_defaults)
        layout.addWidget(reset_btn)

    def _update_steps_label(self, *_) -> None:
        t_start = self._t_start.value()
        t_end = self._t_end.value()
        steps = _calc_steps(t_start, t_end)
        delta_h = (t_end - t_start).total_seconds() / 3600.0 if steps > 0 else 0.0
        if steps <= 0:
            self._steps_label.setText('⚠  End time must be after start time.')
            self._steps_label.setStyleSheet('color: red; font-style: italic;')
        else:
            self._steps_label.setText(f'  Calculated steps: {steps}  ({delta_h:.1f} h  ·  {_T_STEP_MIN:.0f}-min timestep  ·  grid = 10 m)')
            self._steps_label.setStyleSheet('color: #555; font-style: italic;')

    def get_params(self) -> dict:
        return {'t_start': self._t_start.value(), 't_end': self._t_end.value(), 'maxstep': None}

    def reset_to_defaults(self) -> None:
        self._t_start.set_value(_T_START)
        self._t_end.set_value(_T_END)

    def load_settings(self, data: dict) -> None:
        if 't_start' in data:
            v = data['t_start']
            self._t_start.set_value(datetime.fromisoformat(v) if isinstance(v, str) else v)
        if 't_end' in data:
            v = data['t_end']
            self._t_end.set_value(datetime.fromisoformat(v) if isinstance(v, str) else v)
