#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk


class Person(GObject.Object):
    name = GObject.Property(type=str)
    age = GObject.Property(type=int)

    def __init__(self, name, age):
        super().__init__()
        self.name = name
        self.age = age


class DemoApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="demo.textview.columnview")

    def do_activate(self):

        window = Gtk.ApplicationWindow(application=self)
        window.set_default_size(600, 400)

        buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=buffer)
        textview.set_wrap_mode(Gtk.WrapMode.WORD)

        iter = buffer.get_start_iter()

        buffer.insert(iter, "下面是一个嵌入在 TextView 中的 Gtk.ColumnView 表格：\n\n")

        anchor = buffer.create_child_anchor(iter)

        column_view = self.create_table()

        textview.add_child_at_anchor(column_view, anchor)

        iter2 = buffer.get_end_iter()
        buffer.insert(iter2, "\n\n表格结束，继续普通文本。\n")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(textview)

        window.set_child(scrolled)
        window.present()

    def create_table(self):

        store = Gio.ListStore()

        store.append(Person("Alice", 24))
        store.append(Person("Bob", 31))
        store.append(Person("Charlie", 29))

        selection = Gtk.SingleSelection(model=store)

        column_view = Gtk.ColumnView(model=selection)
        column_view.set_vexpand(True)
        column_view.set_hexpand(True)

        # name column
        factory1 = Gtk.SignalListItemFactory()

        factory1.connect("setup", self.setup_label)
        factory1.connect("bind", self.bind_name)

        col1 = Gtk.ColumnViewColumn(title="Name", factory=factory1)
        column_view.append_column(col1)

        # age column
        factory2 = Gtk.SignalListItemFactory()

        factory2.connect("setup", self.setup_label)
        factory2.connect("bind", self.bind_age)

        col2 = Gtk.ColumnViewColumn(title="Age", factory=factory2)
        column_view.append_column(col2)

        return column_view

    def setup_label(self, factory, list_item):
        label = Gtk.Label()
        label.set_xalign(0)
        list_item.set_child(label)

    def bind_name(self, factory, list_item):
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(item.name)

    def bind_age(self, factory, list_item):
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(str(item.age))


from gi.repository import Gio

app = DemoApp()
app.run()
