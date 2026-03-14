# MCacheBox 
# Copyright (c) 2026 Tito de Barros Junior 
# Licensed under the MIT License

from PySide6.QtWidgets import QApplication
from src.main_window import MainWindow

app = QApplication([])
window = MainWindow()
window.show()
window.adjust_lists()

app.exec()