# __init__.py - QGIS Plugin entry point

def classFactory(iface):
    """Factory function to return the plugin class.
    
    This function is required by QGIS to load the plugin.
    
    Args:
        iface: QGIS interface instance
        
    Returns:
        The plugin class instance
    """
    from .bev_to_qfield_plugin import BEVToQFieldPlugin
    return BEVToQFieldPlugin(iface)
