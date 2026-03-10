import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk


class SearchableTextView(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)

        self.set_title("GTK4 TextView Search Demo")
        self.set_default_size(700, 500)

        self.matches = []
        self.current_index = -1

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(main_box)

        # ================= 搜索栏 =================

        self.search_bar = Gtk.Revealer()
        self.search_bar.set_reveal_child(True)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_margin_top(6)
        search_box.set_margin_bottom(6)
        search_box.set_margin_start(6)
        search_box.set_margin_end(6)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)

        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.search_next)

        # 上一个
        self.btn_prev = Gtk.Button(label="<")
        self.btn_prev.set_tooltip_text("Previous")
        self.btn_prev.connect("clicked", lambda x: self.search_previous())

        # 下一个
        self.btn_next = Gtk.Button(label=">")
        self.btn_next.set_tooltip_text("Next")
        self.btn_next.connect("clicked", lambda x: self.search_next())

        # 关闭
        close_btn = Gtk.Button(label="✕")
        close_btn.set_tooltip_text("Close search")
        close_btn.connect("clicked", self.hide_search)

        search_box.append(self.search_entry)
        search_box.append(self.btn_prev)
        search_box.append(self.btn_next)
        search_box.append(close_btn)

        self.search_bar.set_child(search_box)

        main_box.append(self.search_bar)

        # ================= TextView =================

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        self.buffer = self.textview.get_buffer()

        demo_text = "\n".join(
            [
                "GTK4 TextView Search Demo",
                "",
                "Press Ctrl+F to open search.",
                "",
                "Buttons allow previous / next navigation.",
                "This behaves similar to browser search.",
                "",
                "Search words like GTK, search, demo, TextView.",
                "GTK is powerful.",
                "Searching inside GTK TextView is flexible.",
                "GTK search demo again.",
            ]
        )

        self.buffer.set_text(demo_text)

        # 高亮 tag
        self.tag_highlight = self.buffer.create_tag("highlight", background="yellow")

        self.tag_current = self.buffer.create_tag("current_match", background="orange")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)

        main_box.append(scrolled)

        # ================= 键盘监听 =================

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

    # ================= 键盘 =================

    def on_key_pressed(self, controller, keyval, keycode, state):

        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_f:
            self.show_search()
            return True

        if keyval == Gdk.KEY_F3:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self.search_previous()
            else:
                self.search_next()
            return True

        if keyval == Gdk.KEY_Escape:
            self.hide_search(None)
            return True

        return False

    # ================= 搜索 =================

    def on_search_changed(self, entry):

        text = entry.get_text()

        self.clear_highlight()

        if not text:
            return

        start = self.buffer.get_start_iter()

        while True:
            result = start.forward_search(
                text, Gtk.TextSearchFlags.CASE_INSENSITIVE, None
            )

            if not result:
                break

            match_start, match_end = result

            self.buffer.apply_tag(self.tag_highlight, match_start, match_end)

            self.matches.append((match_start, match_end))

            start = match_end

        if self.matches:
            self.current_index = 0
            self.focus_match()

    # ================= 清除高亮 =================

    def clear_highlight(self):

        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()

        self.buffer.remove_tag(self.tag_highlight, start, end)
        self.buffer.remove_tag(self.tag_current, start, end)

        self.matches = []
        self.current_index = -1

    # ================= 聚焦 =================

    def focus_match(self):

        start, end = self.matches[self.current_index]

        buf_start = self.buffer.get_start_iter()
        buf_end = self.buffer.get_end_iter()

        self.buffer.remove_tag(self.tag_current, buf_start, buf_end)

        self.buffer.apply_tag(self.tag_current, start, end)

        self.buffer.select_range(start, end)

        self.textview.scroll_to_iter(start, 0.2, False, 0, 0)

    # ================= 下一个 =================

    def search_next(self, *args):

        if not self.matches:
            return

        self.current_index += 1

        if self.current_index >= len(self.matches):
            self.current_index = 0

        self.focus_match()

    # ================= 上一个 =================

    def search_previous(self):

        if not self.matches:
            return

        self.current_index -= 1

        if self.current_index < 0:
            self.current_index = len(self.matches) - 1

        self.focus_match()

    # ================= 搜索栏 =================

    def show_search(self):

        self.search_bar.set_reveal_child(True)
        self.search_entry.grab_focus()

    def hide_search(self, *args):

        self.search_bar.set_reveal_child(False)
        self.search_entry.set_text("")
        self.clear_highlight()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.textsearch")

    def do_activate(self):
        win = SearchableTextView(self)
        win.present()


app = App()
app.run()
