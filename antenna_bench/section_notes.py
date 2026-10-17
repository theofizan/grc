"""Make stock section Notes into readable banners in this project's GTK GRC.

Only appearance changes. The .grc files still contain ordinary GNU Radio Notes;
no DSP blocks, installed GNU Radio files, or generated radio code are changed.
"""


def install():
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gtk, Pango, PangoCairo

    # Match GRC's normal GUI import order (Actions/Utils depend on it).
    from gnuradio.grc.gui.Platform import Platform
    from gnuradio.grc.gui import Utils
    from gnuradio.grc.gui.canvas.block import Block

    if getattr(Block, "_antenna_section_notes", False):
        return
    original = Block.create_labels

    def create_labels(block, cr=None):
        original(block, cr)
        if block.key != "note" or not block.name.startswith("section_"):
            return
        text = str(block.params["note"].get_evaluated())
        title = text.partition("\n")[0]
        layout = Gtk.DrawingArea().create_pango_layout(title)
        layout.set_font_description(Pango.FontDescription("Sans Bold 14"))
        if cr:
            PangoCairo.update_layout(cr, layout)
        width, height = layout.get_pixel_size()
        block.width, block.height = Utils.align_to_grid((width + 24, height + 16))
        block._surface_layouts = [layout]
        block._surface_layouts_offsets = [(12, 8)]
        block._comment_layout = None
        block._bg_color = (0.91, 0.95, 0.98, 1.0)
        block._border_color = (0.16, 0.35, 0.48, 1.0)
        block._font_color = [0.10, 0.22, 0.31, 1.0]

    Block.create_labels = create_labels
    Block._antenna_section_notes = True
