#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk


class StringItem(GObject.Object):
    value = GObject.Property(type=str)

    def __init__(self, value):
        super().__init__()
        self.value = value


class ListViewWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="GTK4 ListView 示例")
        self.set_default_size(300, 200)

        # 模型
        items = ["苹果", "香蕉", "橙子", "葡萄", "西瓜"]
        list_store = Gio.ListStore.new(StringItem)
        for item in items:
            list_store.append(StringItem(item))

        selection_model = Gtk.SingleSelection.new(list_store)

        # 工厂
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_factory)
        factory.connect("bind", self.bind_factory)

        # ListView
        list_view = Gtk.ListView.new(selection_model, factory)
        self.set_child(list_view)

    def setup_factory(self, factory, list_item):
        label = Gtk.Label()
        list_item.set_child(label)

    def bind_factory(self, factory, list_item):
        label = list_item.get_child()
        item = list_item.get_item()
        label.set_text(item.value)


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.example.ListViewApp")

    def do_activate(self):
        win = ListViewWindow(self)
        win.present()


app = MyApp()
app.run()
