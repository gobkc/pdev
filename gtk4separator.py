import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk


class SeparatorDemoWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Gtk4 Separator 示例")
        self.set_default_size(300, 200)

        # --- 创建一个垂直盒子来垂直排列内容 ---
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        self.set_child(vbox)

        # --- 添加第一个标签 ---
        label1 = Gtk.Label(label="这是上方的区域")
        vbox.append(label1)

        # --- 创建并添加水平分隔线 (Gtk.Separator) ---
        # 创建一个水平分隔线。参数 Gtk.Orientation.HORIZONTAL 定义了方向。
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        # 为了让分隔线更明显，可以给它一些上下边距
        separator.set_margin_top(5)
        separator.set_margin_bottom(5)
        vbox.append(separator)

        # --- 添加第二个标签 ---
        label2 = Gtk.Label(label="这是下方的区域")
        vbox.append(label2)


# --- 应用程序启动代码 (与标准 GTK 应用相同) ---
class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.SeparatorDemo")

    def do_activate(self):
        win = SeparatorDemoWindow(application=self)
        win.present()


if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)
