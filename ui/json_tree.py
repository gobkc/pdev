import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk, Pango


@dataclass
class JsonNode:
    id: str
    key: str
    value: Any
    parent: Optional["JsonNode"] = None
    children: List["JsonNode"] = field(default_factory=list)
    expanded: bool = True

    def is_leaf(self):
        return not isinstance(self.value, (dict, list))


class JsonTree(Gtk.TextView):
    THEMES = {
        "light": {
            "key": "#9c27b0",
            "string": "#e91e63",
            "number": "#2e7d32",
            "boolean": "#f57c00",
            "null": "#757575",
            "icon": "#1976d2",
            "bracket": "#1e88e5",
            "comma": "#616161",
        },
        "dark": {
            "key": "#ce93d8",
            "string": "#f48fb1",
            "number": "#81c784",
            "boolean": "#ffb74d",
            "null": "#bdbdbd",
            "icon": "#64b5f6",
            "bracket": "#4fc3f7",
            "comma": "#9e9e9e",
        },
    }

    TAGS = ["key", "string", "number", "boolean", "null", "icon", "bracket", "comma"]

    def __init__(self, data=None):
        super().__init__()

        self.set_monospace(True)
        self.set_editable(True)
        self.set_wrap_mode(Gtk.WrapMode.NONE)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self.buffer = self.get_buffer()
        self.buffer.set_enable_undo(True)

        self._theme = "light"
        self.node_map = {}
        self.icon_ranges = []
        self._undo_stack = []

        self.root = self._build(data or {})
        self._create_tags()
        self._render()
        self._init_events()

    def _init_events(self):
        click = Gtk.GestureClick()
        click.set_button(0)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

    def set_theme(self, theme):
        if theme not in self.THEMES or self._theme == theme:
            return
        self._theme = theme
        cursor = self._cursor_offset()
        self._create_tags()
        self._render()
        self._restore_cursor(cursor)

    def _create_tags(self):
        table = self.buffer.get_tag_table()

        for name in self.TAGS:
            tag = table.lookup(name)
            if tag:
                table.remove(tag)

        colors = self.THEMES[self._theme]

        def add(name, color, weight=None):
            t = Gtk.TextTag.new(name)
            t.set_property("foreground", color)
            if weight:
                t.set_property("weight", weight)
            table.add(t)

        add("key", colors["key"], Pango.Weight.BOLD)
        add("string", colors["string"])
        add("number", colors["number"])
        add("boolean", colors["boolean"])
        add("null", colors["null"])
        add("icon", colors["icon"])
        add("bracket", colors["bracket"])
        add("comma", colors["comma"])

    def _new_id(self):
        return str(uuid.uuid4())

    def _build(self, data, key="root", parent=None):
        node = JsonNode(self._new_id(), key, data, parent)
        self.node_map[node.id] = node

        if isinstance(data, dict):
            node.children = [self._build(v, k, node) for k, v in data.items()]
        elif isinstance(data, list):
            node.children = [self._build(v, "", node) for v in data]

        return node

    def _render(self):
        buf = self.buffer
        buf.set_text("")
        self.icon_ranges.clear()

        def ins(text, tag=None):
            s = buf.get_end_iter().get_offset()
            buf.insert(buf.get_end_iter(), text)
            e = buf.get_end_iter().get_offset()
            if tag:
                buf.apply_tag_by_name(
                    tag, buf.get_iter_at_offset(s), buf.get_iter_at_offset(e)
                )
            return s, e

        def fmt(v):
            if v is None:
                return "null", "null"
            if v is True or v is False:
                return str(v).lower(), "boolean"
            if isinstance(v, str):
                return f'"{v}"', "string"
            if isinstance(v, (int, float)):
                return str(v), "number"
            return str(v), None

        def walk(node, depth=0, is_list=False):
            buf.insert(buf.get_end_iter(), "\t" * depth)

            if node.children:
                icon = "[-] " if node.expanded else "[+] "
                s, e = ins(icon, "icon")
                self.icon_ranges.append((s, e, node.id))

            if node.key != "root" and not is_list:
                ins(f'"{node.key}": ', "key")

            if node.is_leaf():
                text, tag = fmt(node.value)
                ins(text, tag)
            else:
                ins("{" if isinstance(node.value, dict) else "[", "bracket")

            if node.children and node.expanded:
                ins("\n")
                for i, c in enumerate(node.children):
                    walk(c, depth + 1, isinstance(node.value, list))
                    if i < len(node.children) - 1:
                        ins(",", "comma")
                        ins("\n")
                ins("\n" + "\t" * depth)

            if not node.is_leaf():
                ins("}" if isinstance(node.value, dict) else "]", "bracket")

        walk(self.root)

    def _on_click(self, gesture, n_press, x, y):
        ok, it = self.get_iter_at_location(int(x), int(y))
        if not ok:
            return

        off = it.get_offset()

        for s, e, nid in self.icon_ranges:
            if s <= off < e:
                node = self.node_map.get(nid)
                if node:
                    node.expanded = not node.expanded
                    cursor = self._cursor_offset()
                    self._render()
                    self._restore_cursor(cursor)
                return

    def _on_key(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if ctrl and keyval == Gdk.KEY_s:
            self._manual_render()
            return True

        if ctrl and keyval == Gdk.KEY_z:
            if self._undo_stack:
                prev = self._undo_stack.pop()
                self.buffer.begin_irreversible_action()
                self.buffer.set_text(prev)
                self.buffer.end_irreversible_action()
            return True

        return False

    def _manual_render(self):
        text = self.buffer.get_text(*self.buffer.get_bounds(), False)

        self._undo_stack.append(text)

        cleaned = re.sub(r"\[-\]\s*|\[\+\]\s*", "", text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return

        self.node_map.clear()
        self.root = self._build(data)
        self._render()
        self.buffer.place_cursor(self.buffer.get_start_iter())

    def _cursor_offset(self):
        it = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        return it.get_offset()

    def _restore_cursor(self, offset):
        if offset < self.buffer.get_char_count():
            self.buffer.place_cursor(self.buffer.get_iter_at_offset(offset))
