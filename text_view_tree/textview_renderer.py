import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gtk, Pango


class JsonGutterRenderer(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.textview = Gtk.TextView()
        self.textview.set_monospace(True)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_vexpand(True)
        self.textview.set_hexpand(True)

        self.buffer = self.textview.get_buffer()

        self.gutter = Gtk.DrawingArea()
        self.gutter.set_size_request(80, -1)
        self.gutter.set_vexpand(True)
        self.gutter.set_draw_func(self._draw_gutter)

        self.append(self.gutter)
        self.append(self.textview)

        self.fold_regions = []
        self._raw_text = ""

        self.gutter.add_controller(self._click_controller())

        self.buffer.connect("changed", self._on_buffer_changed)

        self._init_tags()

    def _click_controller(self):
        ctrl = Gtk.GestureClick()
        ctrl.set_button(1)
        ctrl.connect("pressed", self._on_click)
        return ctrl

    def _on_click(self, gesture, n, x, y):
        line = self._line_from_y(y)
        region = self._region_at_line(line)
        if not region:
            return

        region["collapsed"] = not region["collapsed"]
        self._apply_fold()
        self.gutter.queue_draw()

    def _on_buffer_changed(self, *args):
        self._raw_text = self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), False
        )

        self._parse_json_regions(self._raw_text)
        self._highlight()
        self.gutter.queue_draw()

    def set_text(self, text: str):
        self._raw_text = text
        self.buffer.set_text(text)

        self._parse_json_regions(text)
        self._highlight()
        self.gutter.queue_draw()

    def _parse_json_regions(self, text: str):
        self.fold_regions.clear()
        stack = []

        in_string = False
        escape = False

        for i, ch in enumerate(text):
            if ch == "\\" and not escape:
                escape = True
                continue

            if ch == '"' and not escape:
                in_string = not in_string

            escape = False

            if in_string:
                continue

            if ch in "{[":
                stack.append((ch, i))

            elif ch in "}]":
                if not stack:
                    continue

                op, start = stack.pop()

                if (op == "{" and ch == "}") or (op == "[" and ch == "]"):
                    start_line = text[:start].count("\n")
                    end_line = text[:i].count("\n")

                    if start_line == end_line:
                        continue

                    self.fold_regions.append(
                        {
                            "start": start,
                            "end": i,
                            "start_line": start_line,
                            "end_line": end_line,
                            "collapsed": False,
                        }
                    )

    def _render_text(self):
        text = self._raw_text

        regions = sorted(self.fold_regions, key=lambda r: r["start"], reverse=True)

        for r in regions:
            if not r["collapsed"]:
                continue

            s, e = r["start"], r["end"]

            inner = text[s : e + 1]

            if inner.startswith("{"):
                repl = "{…}"
            elif inner.startswith("["):
                repl = "[…]"
            else:
                repl = "…"

            text = text[:s] + repl + text[e + 1 :]

        return text

    def _apply_fold(self):
        rendered = self._render_text()

        self.buffer.handler_block_by_func(self._on_buffer_changed)
        self.buffer.set_text(rendered)
        self.buffer.handler_unblock_by_func(self._on_buffer_changed)
        self._sync_fold_regions_with_buffer(rendered)

        self._highlight()

    def _sync_fold_regions_with_buffer(self, rendered):
        if any(r["collapsed"] for r in self.fold_regions):
            self._update_fold_positions(rendered)
        else:
            self._parse_json_regions(self._raw_text)

    def _update_fold_positions(self, rendered):
        collapsed_regions = sorted(
            [r for r in self.fold_regions if r["collapsed"]],
            key=lambda r: r["start"],
            reverse=True,
        )
        search_from = 0
        text = rendered
        for r in collapsed_regions:
            first_char = self._raw_text[r["start"]]
            marker = "{…}" if first_char == "{" else "[…]"
            pos = text.find(marker, search_from)
            if pos != -1:
                line_num = text[:pos].count("\n")
                r["start_line"] = line_num
                search_from = pos + len(marker)

    def _draw_gutter(self, area, cr, w, h):
        buffer = self.buffer
        start = buffer.get_start_iter()

        line = start.copy()

        while True:
            line_num = line.get_line()

            rect = self.textview.get_iter_location(line)
            _, y = self.textview.buffer_to_window_coords(
                Gtk.TextWindowType.TEXT, rect.x, rect.y
            )

            cr.set_font_size(12)
            cr.set_source_rgb(0.4, 0.4, 0.4)
            cr.move_to(5, y + 12)
            cr.show_text(str(line_num + 1))

            region = self._region_at_line(line_num)
            if region:
                icon = "−" if not region["collapsed"] else "+"
                cr.set_font_size(16)
                cr.set_source_rgb(0.2, 0.4, 0.9)
                cr.move_to(50, y + 14)
                cr.show_text(icon)

            if not line.forward_line():
                break

    def _line_from_y(self, y):
        try:
            bx, by = self.textview.window_to_buffer_coords(
                Gtk.TextWindowType.TEXT, 0, int(y)
            )

            it = self.textview.get_iter_at_location(bx, by)

            if isinstance(it, tuple):
                it = it[-1]

            if hasattr(it, "get_line"):
                return it.get_line()

            if isinstance(it, int):
                return self.buffer.get_iter_at_offset(it).get_line()

            return it.get_line()

        except Exception:
            return int(y // 18)

    def _region_at_line(self, line):
        for r in self.fold_regions:
            if r["start_line"] == line:
                return r
        return None

    def _init_tags(self):
        table = self.buffer.get_tag_table()

        def add(name, color):
            tag = Gtk.TextTag.new(name)
            tag.set_property("foreground", color)
            table.add(tag)

        add("string", "#e91e63")
        add("number", "#2e7d32")

    def _highlight(self):
        text = self._raw_text

        start, end = self.buffer.get_bounds()
        self.buffer.remove_all_tags(start, end)

        for m in re.finditer(r'"[^"]*"', text):
            self.buffer.apply_tag_by_name(
                "string",
                self.buffer.get_iter_at_offset(m.start()),
                self.buffer.get_iter_at_offset(m.end()),
            )

        for m in re.finditer(r"\b\d+\b", text):
            self.buffer.apply_tag_by_name(
                "number",
                self.buffer.get_iter_at_offset(m.start()),
                self.buffer.get_iter_at_offset(m.end()),
            )


class DemoApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.JsonGutterDemo")

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(900, 600)

        renderer = JsonGutterRenderer()

        renderer.set_text("""
{
  "name": "demo",
  "user": {
    "id": 123,
    "tags": ["a", "b", "c"],
    "profile": {
      "age": 18,
      "city": "Singapore"
    }
  },
  "active": true
}
""")

        win.set_child(renderer)
        win.present()


if __name__ == "__main__":
    app = DemoApp()
    app.run(None)
