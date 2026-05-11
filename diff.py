import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def on_compare_clicked(button, entry1, entry2, textview):
    """比较两个逗号分隔的字符串，并在 textview 中显示差异（不显示共同部分）"""
    text1 = entry1.get_text()
    text2 = entry2.get_text()

    # 拆分为集合，去除空白项并去前后空格
    set1 = {item.strip() for item in text1.split(",") if item.strip()}
    set2 = {item.strip() for item in text2.split(",") if item.strip()}

    only_in_first = set1 - set2
    only_in_second = set2 - set1

    # 构造差异消息（不包含共同项）
    if not only_in_first and not only_in_second:
        diff_text = "两个输入包含的内容完全一致。"
    else:
        lines = []
        if only_in_first:
            lines.append(f"只在第一个输入中出现：{', '.join(sorted(only_in_first))}")
        if only_in_second:
            lines.append(f"只在第二个输入中出现：{', '.join(sorted(only_in_second))}")
        diff_text = "\n".join(lines)

    # 更新 TextView 内容
    buffer = textview.get_buffer()
    buffer.set_text(diff_text)


class CompareApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.commastrcomparer")

    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self, title="逗号分隔内容比较")
        window.set_default_size(500, 320)

        # 主垂直容器
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        # 两个输入框
        entry1 = Gtk.Entry()
        entry1.set_placeholder_text("请输入第一个逗号分隔的字符串")
        vbox.append(entry1)

        entry2 = Gtk.Entry()
        entry2.set_placeholder_text("请输入第二个逗号分隔的字符串")
        vbox.append(entry2)

        # 比较按钮
        btn_compare = Gtk.Button(label="比较")

        # 创建 ScrolledWindow 包含 TextView，用于显示差异
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)  # 允许垂直扩展
        textview = Gtk.TextView()
        textview.set_editable(False)  # 只读
        textview.set_wrap_mode(Gtk.WrapMode.WORD)  # 自动换行
        textview.set_monospace(True)  # 等宽字体便于阅读

        scrolled.set_child(textview)

        # 连接按钮信号，传递两个 Entry 和 TextView
        btn_compare.connect("clicked", on_compare_clicked, entry1, entry2, textview)

        # 组装界面
        vbox.append(btn_compare)
        vbox.append(scrolled)

        window.set_child(vbox)
        window.present()


if __name__ == "__main__":
    app = CompareApp()
    app.run()
