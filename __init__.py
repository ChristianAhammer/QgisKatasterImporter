def classFactory(iface):
    from .kataster_converter import KatasterConverterPlugin
    return KatasterConverterPlugin(iface)
