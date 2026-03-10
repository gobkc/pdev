import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk, Pango  # 需要导入 Pango


class CustomLabelWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("自定义整行标签示例")
        self.set_default_size(400, 300)

        # --- 创建一个垂直盒子作为主容器 ---
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        self.set_child(vbox)

        # --- 1. 创建第一个标签：演示基础效果 ---
        label1 = Gtk.Label()
        # 设置文本内容（包含较长文本以演示换行）
        label1.set_label(
            "这是一个会自动换行的整行标签。它应该填满整个宽度，并有40px的内边距、背景色和加粗文字。"
        )
        # 启用自动换行
        label1.set_wrap(True)
        # 设置换行模式为按单词边界换行（使用 Pango.WrapMode）
        label1.set_wrap_mode(Pango.WrapMode.WORD_CHAR)  # 修正：使用 Pango.WrapMode
        # 设置水平扩展为True，使其填满父容器的宽度
        label1.set_hexpand(True)
        # 设置对齐方式（可选，左对齐）
        label1.set_halign(Gtk.Align.FILL)

        # 添加一个自定义的CSS类
        label1.get_style_context().add_class("custom-label")
        vbox.append(label1)

        # --- 2. 创建第二个标签：演示不同文本长度下的效果 ---
        label2 = Gtk.Label(label="短文本示例")
        label2.set_wrap(True)
        label2.set_wrap_mode(Pango.WrapMode.WORD_CHAR)  # 修正：使用 Pango.WrapMode
        label2.set_hexpand(True)
        label2.set_halign(Gtk.Align.FILL)
        label2.get_style_context().add_class("custom-label")
        vbox.append(label2)

        # --- 3. 创建第三个标签：演示非常长的连续字符换行 ---
        label3 = Gtk.Label(
            label="这是一个非常长的单词WithoutSpacesThatWillAlsoWrap按照字符边界换行BecauseWordWrapWontWork"
        )
        label3.set_wrap(True)
        label3.set_wrap_mode(
            Pango.WrapMode.CHAR
        )  # 修正：使用 Pango.WrapMode.CHAR 按字符换行
        label3.set_hexpand(True)
        label3.set_halign(Gtk.Align.FILL)
        label3.get_style_context().add_class("custom-label")
        vbox.append(label3)

        # --- 4. 加载CSS样式 ---
        css_provider = Gtk.CssProvider()
        css_data = """
        .custom-label {
            background-color: #f0f0f0;  /* 浅灰色背景 */
            padding: 40px;               /* 40px 内边距 */
            font-weight: bold;           /* 加粗文字 */
            border-radius: 8px;          /* 可选：添加圆角使其更美观 */
            margin-bottom: 5px;           /* 可选：标签之间的间距 */
        }
        """
        css_provider.load_from_data(css_data.encode("utf-8"))

        # 将CSS应用到整个窗口（也可以更精确地应用到特定控件）
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


# --- 应用程序启动代码 ---
class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.CustomLabelDemo")

    def do_activate(self):
        win = CustomLabelWindow(application=self)
        win.present()


if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)
