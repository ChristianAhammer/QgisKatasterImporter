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

from .bev_to_qfield import BEVToQFieldConfig, BEVToQField


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
        self.setGeometry(100, 100, 750, 650)
        
        self.worker_thread = None
        self.converter = None
        self.config = None
        self.base_path = None  # Will be selected by user
        
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
        layout.addSpacing(10)
        
        # Base folder selection
        folder_group = QGroupBox("Select QGIS Folder")
        folder_layout = QHBoxLayout()
        
        self.folder_path_display = QLabel("(Not selected - please browse)")
        self.folder_path_display.setStyleSheet("color: #CC0000; font-style: italic; padding: 5px;")
        self.folder_path_display.setMinimumHeight(30)
        
        self.btn_browse_folder = QPushButton("Browse...")
        self.btn_browse_folder.setMaximumWidth(120)
        self.btn_browse_folder.clicked.connect(self.browse_base_folder)
        
        folder_layout.addWidget(QLabel("Path:"), 0)
        folder_layout.addWidget(self.folder_path_display, 1)
        folder_layout.addWidget(self.btn_browse_folder, 0)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        
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
            "ℹ️ Selected folder should contain:\n"
            "  • 01_BEV_Rohdaten/ (your input files go here)\n"
            "  • 02_QGIS_Processing/ (optional NTv2/geoid grids)\n"
            "\n"
            "After clicking 'Start Conversion', you'll be asked to select\n"
            "which data folder to convert from 01_BEV_Rohdaten/"
        )
        info_text.setStyleSheet("background-color: #F0F0F0; padding: 10px; border-radius: 3px;")
        layout.addWidget(info_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Output text
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier", 9))
        self.output_text.setMaximumHeight(200)
        layout.addWidget(QLabel("Processing Log:"))
        layout.addWidget(self.output_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("Start Conversion")
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.btn_start)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_conversion)
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setEnabled(False)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setMinimumHeight(40)
        button_layout.addWidget(self.btn_close)
        
        layout.addSpacing(10)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def browse_base_folder(self):
        """Open folder browser to select base QGIS folder."""
        # Suggest common paths
        default_path = Path.home() / "Meine Ablage (ca19770610@gmail.com)" / "QGIS"
        if not default_path.exists():
            default_path = Path.home() / "QGIS"
        if not default_path.exists():
            default_path = Path.home()
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select QGIS folder (should contain 01_BEV_Rohdaten, 02_QGIS_Processing, etc.)",
            str(default_path)
        )
        
        if folder:
            self.base_path = folder
            # Display the path (truncate if too long)
            display_path = folder
            if len(folder) > 70:
                parts = Path(folder).parts
                display_path = "..." + str(Path(*parts[-3:]))  # Show last 3 parts
            
            self.folder_path_display.setText(display_path)
            self.folder_path_display.setStyleSheet("color: #000000; font-style: normal; padding: 5px;")
            self.folder_path_display.setToolTip(folder)  # Show full path on hover
    
    def log_output(self, msg: str):
        """Append message to output text."""
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.insertPlainText(msg + "\n")
        self.output_text.ensureCursorVisible()
    
    def start_conversion(self):
        """Start the conversion process."""
        try:
            # Check if user selected a base path
            if not self.base_path:
                QMessageBox.warning(
                    self,
                    "QGIS Folder Not Selected",
                    "Please click 'Browse...' to select your QGIS folder first.\n\n"
                    "It should contain these folders:\n"
                    "  • 01_BEV_Rohdaten/\n"
                    "  • 02_QGIS_Processing/\n\n"
                    "If these don't exist, they will be created."
                )
                return
            
            base_path = self.base_path
            
            # Check if base path exists
            if not Path(base_path).exists():
                QMessageBox.warning(
                    self,
                    "Base Path Not Found",
                    f"QGIS base path not found:\n{base_path}\n\n"
                    "Please create the directory or select a different path."
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
            self.btn_browse_folder.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.output_text.clear()
            
            self.log_output("🔄 Conversion started...")
            self.log_output(f"Base path: {self.config.base}")
            self.log_output(f"Source CRS: {self.config.SRC_CRS}")
            self.log_output(f"Target CRS: {self.config.TGT_CRS}")
            self.log_output("")
            self.log_output("➡️ A folder selection dialog will appear...")
            self.log_output("   Please select a subfolder from: 01_BEV_Rohdaten/")
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
        self.btn_browse_folder.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.log_output("✔️  Conversion complete!")
    
    def conversion_error(self, error: str):
        """Handle conversion error."""
        self.log_output(f"\n❌ ERROR: {error}")
        self.btn_start.setEnabled(True)
        self.btn_browse_folder.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        QgsMessageLog.logMessage(f"Conversion error: {error}", "BEVToQField", 2)
