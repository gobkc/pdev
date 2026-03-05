import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk


class NoteApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.notes.gitapp")
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(1200, 800)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_hexpand(True)
        toolbar.set_vexpand(False)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_valign(Gtk.Align.FILL)
        self.search_entry.set_width_chars(50)
        self.search_entry.connect("activate", self.on_search_icon_activated)
        toolbar.append(self.search_entry)

        css = """
        searchentry {
            background-image: none;
            background-color: #2e2e2e;
            border: none;
            border-radius: 0;
            box-shadow: none;
            padding: 0;
        }

        searchentry entry {
            background-image: none;
            background-color: #2e2e2e;
            border: none;
            border-radius: 0;
            box-shadow: none;
            padding: 4px;
            color: #ffffff;
        }

        searchentry entry:focus {
            background-image: none;
            background-color: #2e2e2e;
            border: none;
            box-shadow: none;
        }

        searchentry entry:backdrop {
            background-image: none;
            background-color: #2e2e2e;
        }

        searchentry entry:icon-secondary {
            -GtkEntry-icon-position: secondary;
        }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def on_search_icon_activated(self, entry):
        print("Search activated:", entry.get_text())


if __name__ == "__main__":
    app = NoteApp()
    app.run()
