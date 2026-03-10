#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gtk, GtkSource


class Demo(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="demo.textview.gtksource")

    def do_activate(self):
        # 设置应用级别的深色主题偏好
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(700, 500)

        # 创建一个垂直盒子来更好地控制布局
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        win.set_child(vbox)

        # 上方的说明文字
        label = Gtk.Label(label="下面是一个嵌入的 Golang 代码编辑器：")
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(10)
        label.set_margin_top(10)
        vbox.append(label)

        # 创建 GtkSource.View 并让它填满剩余空间
        source_view = self.create_sourceview()
        source_view.set_vexpand(True)  # 垂直扩展
        source_view.set_hexpand(True)  # 水平扩展
        vbox.append(source_view)

        # 下方的说明文字
        label2 = Gtk.Label(label="代码结束。")
        label2.set_halign(Gtk.Align.START)
        label2.set_margin_start(10)
        label2.set_margin_bottom(10)
        vbox.append(label2)

        win.present()

    def create_sourceview(self):
        manager = GtkSource.LanguageManager.get_default()
        language = manager.get_language("go")

        source_buffer = GtkSource.Buffer()
        source_buffer.set_language(language)

        # 设置深色主题
        style_manager = GtkSource.StyleSchemeManager.get_default()
        scheme = style_manager.get_scheme("oblivion")
        if scheme:
            source_buffer.set_style_scheme(scheme)

        code = """package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
"""

        source_buffer.set_text(code)

        source_view = GtkSource.View.new_with_buffer(source_buffer)

        source_view.set_show_line_numbers(True)
        source_view.set_monospace(True)

        # 关键：设置扩展属性，但不设置固定大小
        source_view.set_vexpand(True)
        source_view.set_hexpand(True)

        return source_view


app = Demo()
app.run()
