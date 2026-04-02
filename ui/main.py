#!/usr/bin/env python3
import json
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from ui.json_tree import JsonTree


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("JSON Tree Example")
        self.set_default_size(800, 600)

        # Create the JSON tree widget
        sample_data = {
            "name": "example",
            "version": 1.0,
            "test": False,
            "active": True,
            "tags": ["gtk", "json", "tree"],
            "metadata": {"author": "user", "count": 42, "nullable": None},
        }
        self.json_tree = JsonTree(sample_data)
        self.json_tree.set_theme("dark")
        self.json_tree.add_css_class("tree")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .tree{
            padding: 15px;
            background-image: none;
            background: black;
            color:white;
        }
        """)
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Create a scrolled window to hold the tree (since tree can be large)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(self.json_tree)

        # Control buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(6)
        button_box.set_margin_start(6)
        button_box.set_margin_end(6)

        load_btn = Gtk.Button(label="Load Example")
        load_btn.connect("clicked", self.on_load_example)
        button_box.append(load_btn)

        search_entry = Gtk.Entry()
        search_entry.set_placeholder_text("Search...")
        search_entry.connect("changed", self.on_search_changed)
        button_box.append(search_entry)

        print_btn = Gtk.Button(label="Print JSON")
        print_btn.connect("clicked", self.on_print_json)
        button_box.append(print_btn)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(button_box)
        main_box.append(scrolled)

        self.set_child(main_box)

    def on_load_example(self, button):
        new_data = {
            "library": "GTK4",
            "language": "Python",
            "features": ["collapsible", "editable", "searchable"],
            "nested": {"level2": {"level3": "deep value"}},
        }
        self.json_tree.set_json(new_data)

    def on_search_changed(self, entry):
        text = entry.get_text()
        self.json_tree.search(text)

    def on_print_json(self, button):
        data = self.json_tree.get_json()
        print(json.dumps(data, indent=2, ensure_ascii=False))


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.jsontree")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = MainWindow(app)
        win.present()


def main():
    app = MyApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
