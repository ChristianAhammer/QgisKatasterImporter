# bev_converter.py - Converter dialog for QGIS UI

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QTextEdit, QCheckBox, QGroupBox,
    QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from pathlib import Path
import sys
import os

from qgis.gui import QgisInterface
from qgis.core import QgsMessageLog

# Import the converter from parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bev_to_qfield import BEVToQFieldConfig, BEVToQField


class ConverterWorkerThread(QThread):
    """Worker thread for running converter without blocking UI."""
    
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, converter, config):
        super().__init__()
        self.converter = converter
        self.config = config
        self._original_log = None
    
    def run(self):
        """Run converter in background thread."""
        try:
            # Capture converter output
            self._original_log = self.converter.log
            
            def log_with_signal(msg):
                self.progress.emit(msg)
                self._original_log(msg)
            
            self.converter.log = log_with_signal
            
            # Run conversion
            self.converter.run()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            QgsMessageLog.logMessage(f"Converter error: {str(e)}", "BEVToQField", 2)


class BEVToQFieldDialog(QDialog):
    """Main converter dialog for QGIS."""
    
    def __init__(self, iface: QgisInterface, parent=None):
        """Initialize the dialog.
        
        Args:
            iface: QGIS interface instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("BEV to QField Converter")
        self.setGeometry(100, 100, 700, 600)
        
        self.worker_thread = None
        self.converter = None
        self.config = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        
        # Header
        title = QLabel("BEV to QField Converter")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        subtitle = QLabel("Convert Austrian cadastral data (BEV/MGI-GK) to ETRS89/UTM33N for QField")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle_font.setItalic(True)
        subtitle.setFont(subtitle_font)
        layout.addWidget(subtitle)
        layout.addSpacing(15)
        
        # Options group
        options_group = QGroupBox("Processing Options")
        options_layout = QVBoxLayout()
        
        self.check_make_sync = QCheckBox("Create QField sync directory")
        self.check_make_sync.setChecked(True)
        self.check_make_sync.setToolTip("Create folder structure for QField data synchronization")
        options_layout.addWidget(self.check_make_sync)
        
        self.check_clean_sync = QCheckBox("Clean sync directory before processing")
        self.check_clean_sync.setToolTip("Remove existing files from sync directory (subdirs preserved)")
        options_layout.addWidget(self.check_clean_sync)
        
        self.check_open_qgis = QCheckBox("Open QGIS project on completion")
        self.check_open_qgis.setChecked(False)
        self.check_open_qgis.setToolTip("Automatically open the generated project in QGIS")
        options_layout.addWidget(self.check_open_qgis)
        
        self.check_fix_geom = QCheckBox("Fix invalid geometries")
        self.check_fix_geom.setChecked(True)
        self.check_fix_geom.setToolTip("Attempt to repair invalid geometry before processing")
        options_layout.addWidget(self.check_fix_geom)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Info text
        info_text = QLabel(
            "ℹ️ Make sure you have:\n"
            "  • Input data in: 01_BEV_Rohdaten/ folder\n"
            "  • Output will go to: 03_QField_Output/\n"
            "  • Optional NTv2/geoid grids in: 02_QGIS_Processing/grids/"
        )
        layout.addWidget(info_text)
        layout.addSpacing(10)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Output text
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier", 9))
        self.output_text.setMaximumHeight(250)
        layout.addWidget(QLabel("Processing Log:"))
        layout.addWidget(self.output_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("Start Conversion")
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_start.setMinimumHeight(35)
        button_layout.addWidget(self.btn_start)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_conversion)
        self.btn_cancel.setMinimumHeight(35)
        self.btn_cancel.setEnabled(False)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setMinimumHeight(35)
        button_layout.addWidget(self.btn_close)
        
        layout.addSpacing(10)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def log_output(self, msg: str):
        """Append message to output text."""
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.insertPlainText(msg + "\n")
        self.output_text.ensureCursorVisible()
    
    def start_conversion(self):
        """Start the conversion process."""
        try:
            # Get base path from QGIS settings or use default
            qsettings = self.iface.mainWindow().findChild(type(None))
            base_path = r"C:\Users\Christian\Meine Ablage (ca19770610@gmail.com)\QGIS"
            
            # Check if base path exists
            if not Path(base_path).exists():
                QMessageBox.warning(
                    self,
                    "Base Path Not Found",
                    f"QGIS base path not found:\n{base_path}\n\n"
                    "Please create the directory structure or adjust the path."
                )
                return
            
            # Create config
            self.config = BEVToQFieldConfig(base_path)
            
            # Apply UI settings to config
            self.config.MAKE_SYNC_DIR = self.check_make_sync.isChecked()
            self.config.CLEAN_SYNC_DIR = self.check_clean_sync.isChecked()
            self.config.OPEN_QGIS_ON_FINISH = self.check_open_qgis.isChecked()
            self.config.FIX_GEOM = self.check_fix_geom.isChecked()
            
            # Create converter
            self.converter = BEVToQField(self.config)
            
            # Update UI
            self.btn_start.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.output_text.clear()
            
            self.log_output("🔄 Conversion started...")
            self.log_output(f"Base path: {self.config.base}")
            self.log_output(f"Source CRS: {self.config.SRC_CRS}")
            self.log_output(f"Target CRS: {self.config.TGT_CRS}")
            self.log_output("")
            
            # Run in worker thread
            self.worker_thread = ConverterWorkerThread(self.converter, self.config)
            self.worker_thread.progress.connect(self.log_output)
            self.worker_thread.finished.connect(self.conversion_finished)
            self.worker_thread.error.connect(self.conversion_error)
            self.worker_thread.start()
            
        except Exception as e:
            self.log_output(f"❌ Error: {str(e)}")
            self.conversion_error(str(e))
    
    def cancel_conversion(self):
        """Cancel the conversion."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self.log_output("⏹️  Conversion cancelled")
            self.conversion_finished()
    
    def conversion_finished(self):
        """Handle conversion completion."""
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.log_output("✔️  Conversion complete!")
    
    def conversion_error(self, error: str):
        """Handle conversion error."""
        self.log_output(f"\n❌ ERROR: {error}")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        QgsMessageLog.logMessage(f"Conversion error: {error}", "BEVToQField", 2)
