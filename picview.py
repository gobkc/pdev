import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GdkPixbuf, Gtk


class ImageViewer(Gtk.Window):
    def __init__(self):
        super().__init__(title="Image Viewer")

        self.set_default_size(800, 600)

        # 主布局
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.add(vbox)

        # 打开按钮
        open_button = Gtk.Button(label="Open Image")
        open_button.connect("clicked", self.on_open_clicked)
        vbox.pack_start(open_button, False, False, 0)

        # 图片显示区域
        self.image = Gtk.Image()

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.image)

        vbox.pack_start(scrolled, True, True, 0)

    def on_open_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Open Image", parent=self, action=Gtk.FileChooserAction.OPEN
        )

        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )

        # 文件过滤
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Images")

        filter_images.add_mime_type("image/png")
        filter_images.add_mime_type("image/jpeg")
        filter_images.add_mime_type("image/gif")

        dialog.add_filter(filter_images)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()

            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)

            self.image.set_from_pixbuf(pixbuf)

        dialog.destroy()


def main():
    win = ImageViewer()

    win.connect("destroy", Gtk.main_quit)

    win.show_all()

    Gtk.main()


if __name__ == "__main__":
    main()
