"""A small About box: which build is running, and a way to copy that."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtxterm.branding import LOGO_PATH
from qtxterm.version_info import version_string

LOGO_SIZE = 64

COPIED_TEXT = "Copied"


class AboutDialog(QDialog):
    """Shows the running build's version, commit and source location."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About qtxterm")

        self.details = version_string()

        layout = QHBoxLayout(self)

        self.logo = QLabel(self)
        if LOGO_PATH.is_file():
            self.logo.setPixmap(
                QIcon(str(LOGO_PATH)).pixmap(QSize(LOGO_SIZE, LOGO_SIZE))
            )
        self.logo.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.logo)

        right = QVBoxLayout()
        layout.addLayout(right)

        self.text = QLabel(self.details, self)
        # Selectable so the version can be dragged out even without the button,
        # and monospaced so the aligned labels in version_lines() stay aligned.
        self.text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.text.setStyleSheet("font-family: monospace;")
        right.addWidget(self.text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.copy_button = QPushButton("Copy", self)
        self.copy_button.setDefault(True)
        buttons.addButton(self.copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_details)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

    def copy_details(self) -> None:
        """Put the version block on the clipboard, ready to paste into an issue."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(self.details)
        # Confirm in place. A dialog raising another dialog to say "done" is
        # more interruption than a copy button deserves.
        self.copy_button.setText(COPIED_TEXT)
