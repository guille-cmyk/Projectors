from . import ui
from . import projector
from . import operators
from . import sverchok_nodes


def register():
    projector.register()
    operators.register()
    sverchok_nodes.register()
    ui.register()


def unregister():
    ui.unregister()
    sverchok_nodes.unregister()
    operators.unregister()
    projector.unregister()
