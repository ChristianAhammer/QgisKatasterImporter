# bev_to_qfield_plugin.py - Main QGIS plugin class

from PyQt5.QtWidgets import QAction, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSettings
import os
from pathlib import Path

from qgis.core import QgsMessageLog, QgsApplication
from qgis.gui import QgisInterface

from .bev_converter import BEVToQFieldDialog


class BEVToQFieldPlugin:
    """Main plugin class for BEV to QField Converter."""
    
    def __init__(self, iface: QgisInterface):
        """Initialize the plugin.
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.actions = []
        self.menu = "BEV to QField"
        
        QgsMessageLog.logMessage(
            "BEV to QField Plugin initialized",
            "BEVToQField", 0
        )
    
    def initGui(self):
        """Create the GUI elements of the plugin."""
        # Main action
        self.add_action(
            "Convert BEV Data to QField",
            self.run,
            "Convert Austrian BEV cadastral data to QField format",
            parent=self.iface.mainWindow()
        )
        
        # Add separator
        self.iface.addPluginToVectorMenu(self.menu, QAction(None))
        
        # About action
        self.add_action(
            "About BEV to QField",
            self.show_about,
            "About this plugin",
            parent=self.iface.mainWindow()
        )
        
        QgsMessageLog.logMessage(
            "BEV to QField Plugin GUI initialized",
            "BEVToQField", 0
        )
    
    def unload(self):
        """Remove the plugin menu items and icon."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(self.menu, action)
        
        QgsMessageLog.logMessage(
            "BEV to QField Plugin unloaded",
            "BEVToQField", 0
        )
    
    def add_action(self, text: str, callback, tooltip: str = "", parent=None):
        """Add a toolbar icon to the plugin.
        
        Args:
            text: Text for the action
            callback: Function to call when action triggered
            tooltip: Tooltip text
            parent: Parent widget
        """
        action = QAction(text, parent)
        action.triggered.connect(callback)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        
        self.iface.addPluginToVectorMenu(self.menu, action)
        self.actions.append(action)
        
        return action
    
    def run(self):
        """Execute the main converter dialog."""
        try:
            dialog = BEVToQFieldDialog(self.iface)
            dialog.exec_()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error running BEV to QField: {str(e)}",
                "BEVToQField", 2
            )
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to run converter:\n\n{str(e)}"
            )
    
    def show_about(self):
        """Show about dialog."""
        about_text = """
<h3>BEV to QField Converter v1.0.0</h3>
<p>Convert Austrian cadastral data from BEV (MGI/Gauß-Krüger) 
to ETRS89/UTM33N format for QField mobile fieldwork.</p>

<h4>Features:</h4>
<ul>
    <li>Batch processing of multiple vector layers</li>
    <li>Optional NTv2 grid-based coordinate transformation</li>
    <li>Orthometric height calculation using geoid grid</li>
    <li>Automatic QGIS project creation</li>
    <li>BEV orthofoto (basemap.at) WMTS integration</li>
    <li>QField sync directory preparation</li>
</ul>

<h4>Author:</h4>
<p>Christian Ahammer<br/>
<a href="https://github.com/ChristianAhammer/bev-qfield-workbench">
GitHub Repository</a></p>

<p style="font-size: 0.9em; color: gray;">
QGIS 3.40+ | Licensed under the same terms as QGIS</p>
"""
        QMessageBox.about(
            self.iface.mainWindow(),
            "About BEV to QField Converter",
            about_text
        )
