from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

USAGE_PATH = Path(__file__).parent / "assets" / "USAGE.md"


def load_usage_text() -> str:
    """Read the packaged usage guide, degrading to a readable message on failure.

    Lives in assets/ rather than the repo README so it ships inside the wheel
    and is available from an installed copy, not just a source checkout.
    """
    try:
        return USAGE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return f"# Usage\n\nCould not load the usage guide from `{USAGE_PATH}`:\n\n`{exc}`"


class HelpDialog(QDialog):
    """Renders the packaged usage guide as markdown."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("qtxterm Usage")
        self.resize(760, 620)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        self.browser.setMarkdown(load_usage_text())
        layout.addWidget(self.browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
