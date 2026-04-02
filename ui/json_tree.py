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
    # 两套主题配色
    THEMES = {
        "light": {
            "background": "white",
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
            "background": "black",
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

    def __init__(self, data=None):
        super().__init__()

        self.set_monospace(True)
        self.set_editable(True)
        self.set_cursor_visible(True)
        self.set_wrap_mode(Gtk.WrapMode.NONE)
        self.set_vexpand(True)
        self.set_hexpand(True)

        # 当前使用的主题
        self._current_theme = "light"

        buf = self.get_buffer()
        buf.set_enable_undo(True)

        drag = Gtk.DragSource()
        drag.set_actions(Gdk.DragAction(0))
        self.add_controller(drag)

        self.node_map = {}
        self.icon_ranges = []
        self.root = self._build(data if data else {})

        self._create_tags()  # 根据当前主题创建标签
        self._render()

        click = Gtk.GestureClick()
        click.set_button(0)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def set_theme(self, theme_name: str):
        """切换主题，theme_name 必须是 'light' 或 'dark'"""
        if theme_name not in self.THEMES:
            raise ValueError("主题只能是 'light' 或 'dark'")
        if self._current_theme == theme_name:
            return
        self._current_theme = theme_name
        # 重新创建所有标签
        self._create_tags()
        # 保留当前光标位置并重新渲染
        buf = self.get_buffer()
        cursor_iter = buf.get_iter_at_mark(buf.get_insert())
        cursor_offset = cursor_iter.get_offset()
        self._render()
        # 恢复光标（如果原位置仍有效）
        if cursor_offset < buf.get_char_count():
            buf.place_cursor(buf.get_iter_at_offset(cursor_offset))
        else:
            buf.place_cursor(buf.get_end_iter())

    def _create_tags(self):
        """根据当前主题创建所有文本标签，会先清除旧标签"""
        buf = self.get_buffer()
        table = buf.get_tag_table()

        # 移除所有自定义标签（保留默认标签，但我们的标签都是自定义的）
        # 注意：不能直接遍历删除，因为迭代过程中修改集合会有问题
        tags_to_remove = []
        # 获取所有标签名（需要遍历）
        # TagTable 没有提供直接获取所有标签的方法，我们通过已知标签名来清除
        known_tags = [
            "key",
            "string",
            "number",
            "boolean",
            "null",
            "icon",
            "bracket",
            "comma",
        ]
        for tag_name in known_tags:
            tag = table.lookup(tag_name)
            if tag:
                tags_to_remove.append(tag)
        for tag in tags_to_remove:
            table.remove(tag)

        # 获取当前主题的配色
        colors = self.THEMES[self._current_theme]

        # 创建新标签
        def make_tag(name, color, weight=None):
            if not table.lookup(name):
                tag = Gtk.TextTag.new(name)
                tag.set_property("foreground", color)
                if weight:
                    tag.set_property("weight", weight)
                table.add(tag)
            return table.lookup(name)

        make_tag("key", colors["key"], Pango.Weight.BOLD)
        make_tag("string", colors["string"])
        make_tag("number", colors["number"])
        make_tag("boolean", colors["boolean"])
        make_tag("null", colors["null"])
        make_tag("icon", colors["icon"])
        make_tag("bracket", colors["bracket"])
        make_tag("comma", colors["comma"])

    def _new_id(self):
        return str(uuid.uuid4())

    def _build(self, data, key="root", parent=None):
        node = JsonNode(self._new_id(), key, data, parent)
        self.node_map[node.id] = node

        if isinstance(data, dict):
            for k, v in data.items():
                c = self._build(v, k, node)
                node.children.append(c)
        elif isinstance(data, list):
            for v in data:
                c = self._build(v, "", node)
                node.children.append(c)

        return node

    def _insert_with_tag(self, buf, text, tag_name):
        """在当前光标位置插入文本并立即应用指定标签"""
        start = buf.get_end_iter().get_offset()
        buf.insert(buf.get_end_iter(), text)
        end = buf.get_end_iter().get_offset()
        if start < end:
            buf.apply_tag_by_name(
                tag_name,
                buf.get_iter_at_offset(start),
                buf.get_iter_at_offset(end),
            )
        return start, end

    def _render(self):
        buf = self.get_buffer()
        buf.begin_user_action()

        buf.set_text("")
        self.icon_ranges.clear()

        def walk(node, depth=0, parent_is_list=False):
            indent = "\t" * depth
            buf.insert(buf.get_end_iter(), indent)

            # 处理折叠/展开图标
            if node.children:
                start = buf.get_end_iter().get_offset()
                icon_text = "[-] " if node.expanded else "[+] "
                buf.insert(buf.get_end_iter(), icon_text)
                end = buf.get_end_iter().get_offset()
                self.icon_ranges.append((start, end, node.id))
                # 应用图标高亮
                buf.apply_tag_by_name(
                    "icon",
                    buf.get_iter_at_offset(start),
                    buf.get_iter_at_offset(end),
                )

            # 处理 key (如果存在且不是列表项)
            if node.key != "root" and not parent_is_list:
                ks = buf.get_end_iter().get_offset()
                buf.insert(buf.get_end_iter(), f'"{node.key}": ')
                ke = buf.get_end_iter().get_offset()
                buf.apply_tag_by_name(
                    "key",
                    buf.get_iter_at_offset(ks),
                    buf.get_iter_at_offset(ke),
                )

            # 处理值（叶子节点）
            if node.is_leaf():
                vs = buf.get_end_iter().get_offset()
                buf.insert(buf.get_end_iter(), self._fmt(node.value))
                ve = buf.get_end_iter().get_offset()

                if isinstance(node.value, str):
                    tag = "string"
                elif isinstance(node.value, (int, float)):
                    tag = "number"
                elif isinstance(node.value, bool):
                    tag = "boolean"
                elif node.value is None:
                    tag = "null"
                else:
                    tag = None

                if tag:
                    buf.apply_tag_by_name(
                        tag,
                        buf.get_iter_at_offset(vs),
                        buf.get_iter_at_offset(ve),
                    )
            else:
                # 非叶子节点，输出开括号
                bracket_char = "{" if isinstance(node.value, dict) else "["
                self._insert_with_tag(buf, bracket_char, "bracket")

            # 递归处理子节点
            if node.children and node.expanded:
                buf.insert(buf.get_end_iter(), "\n")
                for i, c in enumerate(node.children):
                    walk(c, depth + 1, isinstance(node.value, list))
                    if i != len(node.children) - 1:
                        # 插入逗号和换行，逗号单独高亮
                        buf.insert(buf.get_end_iter(), ",")
                        # 应用逗号高亮到刚刚插入的逗号
                        comma_end = buf.get_end_iter().get_offset()
                        buf.apply_tag_by_name(
                            "comma",
                            buf.get_iter_at_offset(comma_end - 1),
                            buf.get_iter_at_offset(comma_end),
                        )
                        buf.insert(buf.get_end_iter(), "\n")
                buf.insert(buf.get_end_iter(), "\n")
                buf.insert(buf.get_end_iter(), indent)

            # 处理闭括号（非叶子节点）
            if not node.is_leaf():
                bracket_char = "}" if isinstance(node.value, dict) else "]"
                self._insert_with_tag(buf, bracket_char, "bracket")

        walk(self.root)
        buf.end_user_action()

    def _on_click(self, gesture, n_press, x, y):
        ok, it = self.get_iter_at_location(int(x), int(y))
        if not ok:
            return

        offset = it.get_offset()

        for s, e, nid in self.icon_ranges:
            if s <= offset < e:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)

                node = self.node_map.get(nid)
                if node and node.children:
                    node.expanded = not node.expanded

                    buf = self.get_buffer()
                    cur = buf.get_iter_at_mark(buf.get_insert())
                    off = cur.get_offset()

                    self._render()

                    if off < buf.get_char_count():
                        buf.place_cursor(buf.get_iter_at_offset(off))
                return

    def _on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        alt = state & Gdk.ModifierType.ALT_MASK

        if ctrl and keyval == Gdk.KEY_s:
            self._manual_render()
            return True
        if ctrl and alt and keyval == Gdk.KEY_l:
            self._manual_render()
            return True
        return False

    def _manual_render(self):
        buf = self.get_buffer()
        text = buf.get_text(*buf.get_bounds(), False)
        cleaned = re.sub(r"\[-\]\s*|\[\+\]\s*", "", text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return

        self.node_map.clear()
        self.root = self._build(data)
        self._render()
        buf.place_cursor(buf.get_start_iter())

    def _fmt(self, v):
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)
