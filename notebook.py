#!/usr/bin/env python3
# 依赖安装 sudo apt install libgtksourceview-5-dev gir1.2-gtksource-5
import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from functools import partial

import gi

gi.require_version("GtkSource", "5")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, GtkSource, Pango

HOME_DIR = os.path.expanduser("~")
APP_DIR = os.path.join(HOME_DIR, ".local/.books")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
GIT_DIR = os.path.join(APP_DIR, "git")


class CategoryItem(GObject.Object):
    name = GObject.Property(type=str)

    def __init__(self, name):
        super().__init__()
        self.name = name


class NoteItem(GObject.Object):
    title = GObject.Property(type=str)
    path = GObject.Property(type=str)

    def __init__(self, title, path):
        super().__init__()
        self.title = title
        self.path = path


class NoteApp(Gtk.Application):
    def __init__(self):
        self._markdown_render_timeout_id = None
        super().__init__(application_id="com.notes.gitapp")
        self.connect("activate", self.on_activate)
        self.config = {"repo": "", "user": "", "token": ""}
        self.categories = []
        self.notes = {}
        self.current_category = None
        self.current_note = None

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.config = json.load(f)
        else:
            os.makedirs(APP_DIR, exist_ok=True)
            self.save_config()

    def save_config(self):
        os.makedirs(APP_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def run_git_async(self, func):
        threading.Thread(target=func, daemon=True).start()

    def clone_or_pull_repo(self):
        os.makedirs(APP_DIR, exist_ok=True)
        url = self.config["repo"]
        if self.config["user"] and self.config["token"]:
            parts = url.split("://")
            if len(parts) == 2:
                url = f"{parts[0]}://{self.config['user']}:{self.config['token']}@{parts[1]}"
        if not os.path.exists(GIT_DIR):
            subprocess.run(["git", "clone", url, GIT_DIR])
        else:
            self.git_pull()

    def git_pull(self):
        try:
            subprocess.run(["git", "-C", GIT_DIR, "pull"])
        except Exception as e:
            print(e)

    def git_push(self):
        subprocess.run(["git", "-C", GIT_DIR, "add", "."])
        subprocess.run(["git", "-C", GIT_DIR, "commit", "-m", "Auto commit"])
        subprocess.run(["git", "-C", GIT_DIR, "push"])

    def fetch_repo(self, button):
        self.run_git_async(
            lambda: (
                self.clone_or_pull_repo(),
                self.git_push(),
                GLib.idle_add(self.load_notes),
            )
        )

    def load_notes(self):
        self.categories = []
        self.notes = {}
        if not os.path.exists(GIT_DIR):
            return
        for root, dirs, files in os.walk(GIT_DIR):
            if ".git" in dirs:
                dirs.remove(".git")
            rel_root = os.path.relpath(root, GIT_DIR)
            if rel_root == ".":
                continue
            cat = rel_root.split(os.sep)[0]
            if cat not in self.categories:
                self.categories.append(cat)
                self.notes[cat] = []
            for f in files:
                self.notes[cat].append(os.path.join(root, f))
        GLib.idle_add(self.update_category_list)
        if self.categories:
            self.current_category = self.categories[0]
            GLib.idle_add(lambda: self.update_note_list(self.current_category))
            first_notes = self.notes.get(self.current_category)
            if first_notes:
                self.current_note = first_notes[0]
                GLib.idle_add(lambda: self.update_note_content(self.current_note))

    def update_category_list(self, search=None):
        self.category_liststore.remove_all()
        for cat in self.categories:
            if search and search.lower() not in cat.lower():
                continue
            self.category_liststore.append(CategoryItem(cat))
        if (
            self.category_selection.get_selected_item() is None
            and len(self.category_liststore) > 0
        ):
            self.category_selection.set_selected_item(self.category_liststore[0])

    def update_note_list(self, category, search=None):
        self.note_liststore.remove_all()
        for note_file in self.notes.get(category, []):
            title = os.path.basename(note_file)
            self.note_liststore.append(NoteItem(title, note_file))
        if (
            self.note_selection.get_selected_item() is None
            and len(self.note_liststore) > 0
        ):
            self.note_selection.set_selected_item(self.note_liststore[0])

    def update_note_content(self, note_file):
        if not os.path.exists(note_file):
            self.note_textbuffer.set_text("")
            return
        with open(note_file, "r") as f:
            content = f.read()
        render_markdown(self.note_textbuffer, self.note_textview, content)
        stats = os.stat(note_file)
        created = datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        # display_text = (
        #     f"Title: {os.path.basename(note_file)}\nCreated: {created}\n\n{content}"
        # )
        # self.note_textbuffer.set_text(display_text)
        self.edit_box_title_text.set_text(os.path.basename(note_file))
        self.edit_box_time_text_buffer.set_text(created)
        self.edit_box_markdown_text_buffer.set_text(content)

    def on_search_icon_activated(self, search_entry):
        search_text = self.search_entry.get_text().strip()
        if not search_text:
            return

        # 创建弹窗
        dialog = Gtk.Dialog(transient_for=self.window, modal=True)
        dialog.set_title("Search Results")
        dialog.set_default_size(600, 400)

        content_area = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        content_area.append(vbox)

        # ---------------- 上部 Categories ----------------
        cat_label = Gtk.Label(label="Categories")
        cat_label.set_halign(Gtk.Align.START)
        vbox.append(cat_label)

        cat_liststore = Gio.ListStore(item_type=CategoryItem)
        for cat in self.categories:
            if search_text.lower() in cat.lower():
                cat_liststore.append(CategoryItem(cat))

        cat_selection = Gtk.SingleSelection(model=cat_liststore)

        cat_factory = Gtk.SignalListItemFactory()

        def cat_setup(factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            list_item.set_child(label)

        def cat_bind(factory, list_item):
            item = list_item.get_item()
            label = list_item.get_child()
            label.set_text(item.name)

        cat_factory.connect("setup", cat_setup)
        cat_factory.connect("bind", cat_bind)

        cat_listview = Gtk.ListView(model=cat_selection, factory=cat_factory)
        cat_listview.set_vexpand(True)

        cat_scrolled = Gtk.ScrolledWindow()
        cat_scrolled.set_child(cat_listview)
        cat_scrolled.set_vexpand(True)
        vbox.append(cat_scrolled)

        # 双击选择 category
        def on_cat_activated(list_view, position):
            item = cat_selection.get_selected_item()
            if item:
                self.current_category = item.name
                # 高亮主界面的 category 列表
                for i, cat_name in enumerate(self.categories):
                    if cat_name == item.name:
                        self.category_selection.set_selected(i)
                        break
                self.current_note = None
                self.edit_box_title_text.set_text("")
                self.edit_box_time_text_buffer.set_text("")
                self.edit_box_markdown_text_buffer.set_text("")
                dialog.destroy()

        cat_listview.connect("activate", on_cat_activated)

        # ---------------- 下部 Notes ----------------
        note_label = Gtk.Label(label="Notes")
        note_label.set_halign(Gtk.Align.START)
        vbox.append(note_label)

        note_liststore = Gio.ListStore(item_type=NoteItem)
        import os

        for cat_name, notes in self.notes.items():
            for note_file in notes:
                title = os.path.basename(note_file)
                content_match = False
                try:
                    with open(note_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if search_text.lower() in content.lower():
                            content_match = True
                except Exception:
                    pass
                if search_text.lower() in title.lower() or content_match:
                    note_liststore.append(NoteItem(title, note_file))

        note_selection = Gtk.SingleSelection(model=note_liststore)
        note_factory = Gtk.SignalListItemFactory()

        def note_setup(factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            list_item.set_child(label)

        def note_bind(factory, list_item):
            item = list_item.get_item()
            label = list_item.get_child()
            label.set_text(item.title)

        note_factory.connect("setup", note_setup)
        note_factory.connect("bind", note_bind)

        note_listview = Gtk.ListView(model=note_selection, factory=note_factory)
        note_listview.set_vexpand(True)

        note_scrolled = Gtk.ScrolledWindow()
        note_scrolled.set_child(note_listview)
        note_scrolled.set_vexpand(True)
        vbox.append(note_scrolled)

        # 双击选择 note
        def on_note_activated(list_view, position):
            item = note_selection.get_selected_item()
            if item:
                # 找到 note 所在 category
                category_of_note = None
                for cat_name, notes in self.notes.items():
                    if item.path in notes:
                        category_of_note = cat_name
                        break
                if category_of_note:
                    self.current_category = category_of_note
                    # 高亮 category
                    for i, cat_name in enumerate(self.categories):
                        if cat_name == category_of_note:
                            self.category_selection.set_selected(i)
                            break
                    # 高亮 note
                    cat_notes = self.notes.get(category_of_note, [])
                    for j, n_path in enumerate(cat_notes):
                        if n_path == item.path:
                            self.note_selection.set_selected(j)
                            break

                self.current_note = item.path
                self.update_note_content(item.path)
                dialog.destroy()

        note_listview.connect("activate", on_note_activated)

        dialog.show()

    def on_settings_clicked(self, button):
        dialog = Gtk.Dialog(title="Settings", transient_for=self.window, modal=True)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK
        )
        box = dialog.get_content_area()
        grid = Gtk.Grid(
            column_spacing=10,
            row_spacing=10,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
        )
        box.append(grid)
        grid.attach(Gtk.Label(label="Git Repo URL", halign=Gtk.Align.END), 0, 0, 1, 1)
        grid.attach(Gtk.Label(label="User / OAuth2", halign=Gtk.Align.END), 0, 1, 1, 1)
        grid.attach(
            Gtk.Label(label="Token / Personal Token", halign=Gtk.Align.END), 0, 2, 1, 1
        )
        repo_entry = Gtk.Entry(text=self.config.get("repo", ""))
        user_entry = Gtk.Entry(text=self.config.get("user", ""))
        token_entry = Gtk.Entry(text=self.config.get("token", ""))
        grid.attach(repo_entry, 1, 0, 1, 1)
        grid.attach(user_entry, 1, 1, 1, 1)
        grid.attach(token_entry, 1, 2, 1, 1)
        dialog.show()

        def on_response(d, response_id):
            if response_id == Gtk.ResponseType.OK:
                self.config["repo"] = repo_entry.get_text()
                self.config["user"] = user_entry.get_text()
                self.config["token"] = token_entry.get_text()
                self.save_config()
                self.run_git_async(self.clone_or_pull_repo)
                self.run_git_async(self.load_notes)
            d.destroy()

        dialog.connect("response", on_response)

    def on_add_category_clicked(self, button):
        dialog = Gtk.Dialog(title="New Category", transient_for=self.window, modal=True)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Create", Gtk.ResponseType.OK
        )
        box = dialog.get_content_area()
        entry = Gtk.Entry()
        entry.set_placeholder_text("Enter new category name")
        box.append(entry)
        dialog.show()

        def on_response(d, response_id):
            if response_id == Gtk.ResponseType.OK:
                cat_name = entry.get_text().strip()
                if cat_name:
                    new_path = os.path.join(GIT_DIR, cat_name)
                    os.makedirs(new_path, exist_ok=True)
                    self.load_notes()
            d.destroy()

        dialog.connect("response", on_response)

    def on_add_note_clicked(self, button):
        self.edit_box_title_text.set_text("")
        self.edit_box_markdown_text_buffer.set_text("")
        self.edit_box_time_text_buffer.set_text(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def on_activate(self, app):
        self.load_config()
        self.clone_or_pull_repo()
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(1200, 800)
        self.window.maximize()
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        title_label = Gtk.Label(label="Git Notebook")
        header.set_title_widget(title_label)
        self.window.set_titlebar(header)
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", True
        )

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toolbar.set_hexpand(True)
        toolbar.get_style_context().add_class("toolbar")

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search...")
        self.search_entry.set_width_chars(20)
        toolbar.append(self.search_entry)
        self.search_button = Gtk.Button()
        toolbar.append(self.search_button)
        icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        self.search_button.set_child(icon)
        self.search_button.connect("clicked", self.on_search_icon_activated)
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.get_style_context().add_class("toolbar-separator")
        toolbar.append(separator)

        sync_button = Gtk.Button()
        sync_button.get_style_context().add_class("sync-button")
        button_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        button_content.append(icon)
        label = Gtk.Label(label="Sync Remote")
        label.get_style_context().add_class("sync-label")
        button_content.append(label)
        sync_button.connect("clicked", self.on_sync_button_clicked)
        sync_button.set_child(button_content)
        toolbar.append(sync_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.get_style_context().add_class("toolbar-separator")
        toolbar.append(separator)
        settings_button = Gtk.Button(label="⚙")
        settings_button.set_valign(Gtk.Align.CENTER)
        settings_button.connect("clicked", self.on_settings_clicked)
        settings_button.get_style_context().add_class("flat-button")
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)
        toolbar.append(settings_button)

        self.category_liststore = Gio.ListStore.new(CategoryItem)
        self.category_selection = Gtk.SingleSelection.new(self.category_liststore)
        self.category_selection.connect(
            "notify::selected-item", self.on_category_selected_changed
        )
        self.category_factory = Gtk.SignalListItemFactory()
        self.category_factory.connect("setup", self.setup_category_factory)
        self.category_factory.connect("bind", self.bind_category_factory)
        self.category_listview = Gtk.ListView.new(
            self.category_selection, self.category_factory
        )
        self.category_listview.set_name("category-list")
        self.category_listview.set_vexpand(True)

        category_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        category_label = Gtk.Label(label="Categories")
        category_label.set_halign(Gtk.Align.START)
        category_spacer = Gtk.Box()
        category_spacer.set_hexpand(True)
        category_add_btn = Gtk.Button()
        category_add_icon = Gtk.Image.new_from_icon_name("list-add-symbolic")
        category_add_btn.set_child(category_add_icon)
        category_add_btn.connect("clicked", self.on_add_category_clicked)
        category_header.append(category_label)
        category_header.append(category_spacer)
        category_header.append(category_add_btn)
        category_header.set_name("category-header")

        category_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        category_box.append(category_header)
        category_box.append(self.category_listview)

        category_scrolled = Gtk.ScrolledWindow()
        category_scrolled.set_child(category_box)

        self.note_liststore = Gio.ListStore.new(NoteItem)
        self.note_selection = Gtk.SingleSelection.new(self.note_liststore)
        self.note_selection.connect(
            "notify::selected-item", self.on_note_selected_changed
        )
        self.note_factory = Gtk.SignalListItemFactory()
        self.note_factory.connect("setup", self.setup_note_factory)
        self.note_factory.connect("bind", self.bind_note_factory)
        self.note_listview = Gtk.ListView.new(self.note_selection, self.note_factory)
        self.note_listview.set_name("note-list")
        self.note_listview.set_vexpand(True)
        note_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        note_label = Gtk.Label(label="Notes")
        note_label.set_halign(Gtk.Align.START)
        note_spacer = Gtk.Box()
        note_spacer.set_hexpand(True)
        note_add_btn = Gtk.Button()
        note_add_icon = Gtk.Image.new_from_icon_name("list-add-symbolic")  # 内置 icon
        note_add_btn.set_child(note_add_icon)
        note_add_btn.connect("clicked", self.on_add_note_clicked)
        note_header.append(note_label)
        note_header.append(note_spacer)
        note_header.append(note_add_btn)
        note_header.set_name("note-header")
        note_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        note_box.append(note_header)
        note_box.append(self.note_listview)
        note_scrolled = Gtk.ScrolledWindow()
        note_scrolled.set_child(note_box)

        self.note_textbuffer = Gtk.TextBuffer()
        self.note_textview = Gtk.TextView(buffer=self.note_textbuffer)
        self.note_textview.set_editable(False)
        note_scrolled_view = Gtk.ScrolledWindow()
        note_scrolled_view.set_child(self.note_textview)
        self.note_textview.set_left_margin(35)
        self.note_textview.set_right_margin(35)
        self.note_textview.set_top_margin(35)
        self.note_textview.set_bottom_margin(35)
        self.note_textview.set_vexpand(True)
        self.note_textview.set_hexpand(True)
        note_scrolled_view.get_style_context().add_class("note-area")
        self.note_textview.set_name("note-textview")

        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        edit_box.set_hexpand(True)
        edit_box.set_vexpand(True)

        # edit toolbar
        self.edit_tool_bar = Gtk.Revealer()
        self.edit_tool_bar.set_reveal_child(True)
        self.edit_tool_bar.set_name("edit-toolbar")

        self.edit_tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.edit_tool_box.set_margin_top(6)
        self.edit_tool_box.set_margin_bottom(6)
        self.edit_tool_box.set_margin_start(6)
        self.edit_tool_box.set_margin_end(6)
        self.edit_tool_box.set_name("edit-toolbox")

        self.edit_tool_entry = Gtk.SearchEntry()
        self.edit_tool_entry.set_hexpand(True)

        self.edit_tool_save_btn = Gtk.Button()
        edit_tool_save_btn_icon = Gtk.Image.new_from_icon_name("document-save-symbolic")
        self.edit_tool_save_btn.set_child(edit_tool_save_btn_icon)
        edit_tool_save_btn_icon.set_tooltip_text("Save Markdown")
        self.edit_tool_save_btn.connect("clicked", self.on_save_markdown_clicked)
        self.edit_tool_box.append(self.edit_tool_save_btn)

        self.edit_tool_bold_btn = Gtk.Button(label="B")
        self.edit_tool_bold_btn.set_tooltip_text("Bold")
        self.edit_tool_box.append(self.edit_tool_bold_btn)

        self.edit_tool_italic_btn = Gtk.Button(label="I")
        self.edit_tool_italic_btn.set_tooltip_text("Italic")
        self.edit_tool_box.append(self.edit_tool_italic_btn)

        self.edit_tool_underline_btn = Gtk.Button(label="U")
        self.edit_tool_underline_btn.set_tooltip_text("underline")
        self.edit_tool_box.append(self.edit_tool_underline_btn)

        self.edit_tool_strikethrough_btn = Gtk.Button(label="ST")
        self.edit_tool_strikethrough_btn.set_tooltip_text("strikethrough")
        self.edit_tool_box.append(self.edit_tool_strikethrough_btn)

        self.edit_tool_ol_btn = Gtk.Button(label="OL")
        self.edit_tool_ol_btn.set_tooltip_text("Ordered List")
        self.edit_tool_box.append(self.edit_tool_ol_btn)

        self.edit_tool_ul_btn = Gtk.Button(label="UL")
        self.edit_tool_ul_btn.set_tooltip_text("Unordered List")
        self.edit_tool_box.append(self.edit_tool_ul_btn)

        self.edit_tool_link_btn = Gtk.Button(label="L")
        self.edit_tool_link_btn.set_tooltip_text("link")
        self.edit_tool_box.append(self.edit_tool_link_btn)

        self.edit_tool_table_btn = Gtk.Button(label="TB")
        self.edit_tool_table_btn.set_tooltip_text("Table")
        self.edit_tool_box.append(self.edit_tool_table_btn)

        edit_tool_spacer = Gtk.Box()
        edit_tool_spacer.set_hexpand(True)
        self.edit_tool_box.append(edit_tool_spacer)

        self.edit_tool_search_btn = Gtk.Button()
        self.edit_tool_search_btn.connect("clicked", self.show_search)
        edit_tool_search_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        self.edit_tool_search_btn.set_child(edit_tool_search_icon)
        self.edit_tool_search_btn.set_tooltip_text("Search")
        self.edit_tool_box.append(self.edit_tool_search_btn)

        self.edit_tool_bar.set_child(self.edit_tool_box)
        edit_box.append(self.edit_tool_bar)
        # edit toolbar ui结束
        # search bar
        self.edit_search_bar = Gtk.Revealer()
        self.edit_search_bar.set_reveal_child(True)
        self.edit_search_bar.set_name("edit-searchbar")
        edit_search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        edit_search_box.set_margin_top(6)
        edit_search_box.set_margin_bottom(6)
        edit_search_box.set_margin_start(6)
        edit_search_box.set_margin_end(6)
        edit_search_box.set_name("edit-searchbox")

        self.edit_search_entry = Gtk.SearchEntry()
        self.edit_search_entry.set_hexpand(True)
        self.edit_search_entry.connect("search-changed", self.on_search_changed)
        self.edit_search_entry.connect("activate", self.search_next)

        # 上一个
        self.edit_btn_prev = Gtk.Button(label="<")
        self.edit_btn_prev.set_tooltip_text("Previous")
        self.edit_btn_prev.connect("clicked", lambda w: self.search_previous())

        # 下一个
        self.edit_btn_next = Gtk.Button(label=">")
        self.edit_btn_next.set_tooltip_text("Next")
        self.edit_btn_next.connect("clicked", lambda w: self.search_next())

        # 关闭
        edit_close_btn = Gtk.Button(label="✕")
        edit_close_btn.set_tooltip_text("Close search")
        edit_close_btn.connect("clicked", self.hide_search)
        edit_search_box.append(self.edit_search_entry)
        edit_search_box.append(self.edit_btn_prev)
        edit_search_box.append(self.edit_btn_next)
        edit_search_box.append(edit_close_btn)
        self.edit_search_bar.set_child(edit_search_box)
        edit_box.append(self.edit_search_bar)
        # search bar ui结束

        # edit titile bar start
        edit_box_titilebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        edit_box_titilebar.set_hexpand(True)
        edit_box_titilebar.set_name("titlebar")
        edit_box_titile_icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        edit_box_titile_icon.set_name("title-icon")
        edit_box_titilebar.append(edit_box_titile_icon)
        self.edit_box_title_text = Gtk.Entry()
        self.edit_box_title_text.set_placeholder_text("Title...")
        self.edit_box_title_text.set_hexpand(True)
        self.edit_box_title_text.set_vexpand(False)
        self.edit_box_title_text.set_size_request(-1, 20)
        self.edit_box_title_text.set_alignment(0.0)
        self.edit_box_title_text.set_name("title-text")
        edit_box_titilebar.append(self.edit_box_title_text)
        self.edit_box_time_text_buffer = Gtk.TextBuffer()
        edit_box_time_text = Gtk.TextView(buffer=self.edit_box_time_text_buffer)
        edit_box_time_text.set_editable(False)
        edit_box_time_text.set_cursor_visible(False)
        edit_box_time_text.set_wrap_mode(Gtk.WrapMode.NONE)
        edit_box_time_text.set_top_margin(14)
        edit_box_time_text.set_bottom_margin(0)
        edit_box_time_text.set_left_margin(5)
        edit_box_time_text.set_right_margin(15)
        edit_box_time_text.set_size_request(179, 20)
        edit_box_time_text.set_name("time-text")
        edit_box_time_text.set_halign(Gtk.Align.END)

        edit_box_time_icon = Gtk.Image.new_from_icon_name(
            "preferences-system-time-symbolic"
        )
        edit_box_time_icon.set_name("time-icon")
        edit_box_titilebar.append(edit_box_time_icon)

        edit_box_titilebar.append(edit_box_time_text)
        edit_box.append(edit_box_titilebar)
        # edit titlebar end

        self.edit_box_markdown_text_buffer = Gtk.TextBuffer()
        self.edit_box_markdown_text = Gtk.TextView(
            buffer=self.edit_box_markdown_text_buffer
        )
        self.edit_box_markdown_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.edit_box_markdown_text.set_hexpand(True)
        self.edit_box_markdown_text.set_vexpand(True)
        self.edit_box_markdown_text.set_left_margin(35)
        self.edit_box_markdown_text.set_right_margin(35)
        self.edit_box_markdown_text.set_top_margin(35)
        self.edit_box_markdown_text.set_bottom_margin(35)
        self.edit_box_markdown_text.set_name("markdown-text")
        self.edit_box_markdown_text_buffer.connect("changed", self.on_markdown_changed)
        markdown_scrolled = Gtk.ScrolledWindow()
        markdown_scrolled.set_child(self.edit_box_markdown_text)
        markdown_scrolled.set_hexpand(True)
        markdown_scrolled.set_vexpand(True)
        edit_box.append(markdown_scrolled)
        edit_area = edit_box
        note_scrolled_view.set_size_request(300, -1)
        right_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        right_pane.set_start_child(edit_area)
        right_pane.set_end_child(note_scrolled_view)
        right_pane.set_position(-1)
        middle_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        middle_pane.set_start_child(note_scrolled)
        middle_pane.set_end_child(right_pane)
        middle_pane.set_position(300)
        main_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        main_pane.set_start_child(category_scrolled)
        main_pane.set_end_child(middle_pane)
        main_pane.set_position(250)

        default_prompt = "Welcome to Git Notebook Console\nType 'help' for available shortcut key\n1.Ctrl-N\tCreate a new note \n2.Ctrl-+ \tCreate a new category \n3.Ctrl-S \tSave current note \n>"
        self.console_buffer = Gtk.TextBuffer()
        self.console_buffer.set_text(default_prompt)
        self.console_view = Gtk.TextView(buffer=self.console_buffer)
        self.console_view.set_editable(False)
        self.console_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.console_view.get_style_context().add_class("console-area")
        console_scrolled = Gtk.ScrolledWindow()
        console_scrolled.set_child(self.console_view)
        console_scrolled.set_vexpand(False)
        console_scrolled.set_size_request(-1, 150)

        def console_log(text):
            end_iter = self.console_buffer.get_end_iter()
            self.console_buffer.insert(end_iter, text + "\n")
            mark = self.console_buffer.create_mark(
                None, self.console_buffer.get_end_iter(), False
            )
            self.console_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

        self.console_log = console_log

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .main-window ,headerbar {
            background-color: #26282b;
            background-image: none;
            color: white;
        }
        #edit-toolbox,#edit-toolbar,#edit-searchbox,#edit-searchbar{
            background-color: #26282b;
            background-image: none;
        }
        #edit-searchbar{
            border-bottom: 1px solid black;
        }
        #edit-toolbar button, #edit-searchbar button{
            color: #c1c1c1;
            font-weight:bold;
        }
        #edit-toolbar button:hover, #edit-searchbar button:hover{
            color: white;
            background-color: rgba(255,255,255,0.03);
        }
        .toolbar {
            background-color: #26282b;
            border-bottom:1px solid black;
        }
        entry {
            border: none;
            border-radius: 0;
            background-color: #26282b;
            color: #ffffff;
            padding: 4px;
            padding-left:10px;
            padding-right:10px;
            outline: none;
        }
        entry:focus {
            background-color: #26282b;
            -GtkEntry-focus-line-width: 1px;
            -GtkEntry-focus-border: #000000;
            box-shadow: none;
        }
        entry:backdrop {
            background-color: #26282b;
        }
        button {
            border: none;
            background-image: none;
            background-color: #26282b;
            border-radius: 0;
        }
        button:hover {
            background-color: #26282b;
        }
        button:active {
            background-color: #26282b;
        }
        image {
            color: #c1c1c1;
        }
        button:hover image {
            color: #ffffff;
        }

        #category-list {
            background-color: #26282b;
            color: #bcbec4;
        }
        #note-list {
            background-color: #26282b;
            color: #bcbec4;
        }
        #category-header, #note-header {
            padding: 5px;
            padding-left:15px;
            background-color: #26282b;
            color: #bcbec4;
            font-weight: bold;
        }
        #category-header > button, #note-header > button {
            min-width: 24px;
            min-height: 24px;
        }
        .toolbar-separator {
            background-color: black;
            padding: 0;
            margin: 0;
        }
        .sync-button {
            background-color: #26282b;
            border: none;
            border-radius: 0;
            padding: 4px 24px;
            margin: 0;
        }
        .sync-button:hover {
            background-color: #26282b;
        }
        .sync-button:active {
            background-color: #26282b;
        }

        .sync-label {
            font-size: 14px;
            font-weight: bold;
            color: #c1c1c1;
        }
        .sync-button:hover .sync-label{
            color: #ffffff;
        }

        .flat-button {
            border: none;
            background-image: none;
            background-color: #26282b;
            border-radius: 0;
            color: #c1c1c1;
        }
        .flat-button:hover {
            background-color: #26282b;
            color: #ffffff;
        }
        .cate-button {
            border-radius:0;
            border-width:0;
            box-shadow:none;
            background-color:#26282b;
            color:#ffffff;
        }
        GtkSearchEntry {
            border-radius:0;
            border-width:0;
        }
        GtkTextView {
            background-color:#2b2b2b;
            color:#ffffff;
        }
        .right_pane {
            background-color:#191a1c;
        }

        .note-area {
            background-color:#191a1c;
            border-left: 1px solid black;
        }
        .note-area > viewport {
            background-color: #191a1c;
        }
        #note-textview {
            background-color: #191a1c;
        }
        #markdown-text,#titlebar {
            background-color: #191a1c;
        }
        #title-text,#time-text {
            background-color: #26282b;
            color: #bcbec4;
            font-size:14px;
            font-weight:bold;
        }
        #title-icon{
            background-color: #26282b;
            padding-left: 15px;
        }
        #time-icon{
            background-color: #26282b;
        }
        #time-text{
            border-left:0px;
            color: #8e8e99;
            font-size: 12px;
            font-style: italic;
            text-align:right;
        }
        .console-area {
            padding: 20px;
            color: #1bd66c;
            background-color: #191a1c;
            border-top:1px solid black;
            font-size: 13px;
            caret-color: #1bd66c;
        }
        .console-area:selected {
            background-color: #4a90e2;
            color: #ffffff;
        }
        .console-area textview {
            background-color: #26282b;
            color: #1bd66c;
            font-family: monospace;
            font-size: 13px;
        }
        .console-area textview text {
            background-color: #26282b;
            color: #1bd66c;
        }
        .console-area textview text:backdrop,
        .console-area textview text:insensitive,
        .console-area textview text:active,
        .console-area textview text:hover {
            color: #1bd66c;
        }
        .console-area textview text:selected {
            background-color: #4a90e2;
            color: #ffffff;
        }
        .console-area textview text:selected:focus {
            background-color: #4a90e2;
            color: #ffffff;
        }
        .console-area textview {
            caret-color: #1bd66c;
        }
        """)
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_vexpand(True)
        vbox.append(toolbar)
        vbox.append(main_pane)
        vbox.append(console_scrolled)
        self.window.set_child(vbox)
        self.load_notes()
        self.window.show()
        self.bind_global_shortcuts()
        self.bind_markdown_buttons()

    def bind_markdown_buttons(self):
        buffer = self.edit_box_markdown_text_buffer  # TextBuffer 已经是 buffer

        def wrap_selection(prefix, suffix=None):
            if suffix is None:
                suffix = prefix
            bounds = buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                text = buffer.get_text(start, end, True)
                buffer.delete(start, end)
                buffer.insert(start, f"{prefix}{text}{suffix}")
            else:
                iter_ = buffer.get_iter_at_mark(buffer.get_insert())
                buffer.insert(iter_, f"{prefix}{suffix}")

        def insert_list(ordered=False):
            start_iter = buffer.get_iter_at_mark(buffer.get_insert())
            line_start = start_iter.copy()
            line_start.set_line_offset(0)
            line_end = start_iter.copy()
            line_end.forward_to_line_end()
            line_text = buffer.get_text(line_start, line_end, True)
            prefix = "1. " if ordered else "- "
            buffer.delete(line_start, line_end)
            buffer.insert(line_start, f"{prefix}{line_text}")

        def insert_link():
            bounds = buffer.get_selection_bounds()
            dialog = Gtk.Dialog(title="Insert Link", transient_for=self.window)
            dialog.add_buttons(
                "OK", Gtk.ResponseType.OK, "Cancel", Gtk.ResponseType.CANCEL
            )

            content_area = dialog.get_content_area()
            name_entry = Gtk.Entry()
            name_entry.set_placeholder_text("Link Text")
            url_entry = Gtk.Entry()
            url_entry.set_placeholder_text("URL")
            content_area.append(name_entry)
            content_area.append(url_entry)

            dialog.show()

            # GTK4 处理 response 信号
            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.OK:
                    link_text = name_entry.get_text()
                    url = url_entry.get_text()
                    buffer_iter = buffer.get_iter_at_mark(buffer.get_insert())
                    if bounds:
                        start, end = bounds
                        selected_text = buffer.get_text(start, end, True)
                        buffer.delete(start, end)
                        buffer.insert(start, f"[{selected_text}]({url})")
                    else:
                        buffer.insert(buffer_iter, f"[{link_text}]({url})")
                dialog.destroy()

            dialog.connect("response", on_response)

        def insert_table():
            dialog = Gtk.Dialog(title="Insert Table", transient_for=self.window)
            dialog.add_buttons(
                "OK", Gtk.ResponseType.OK, "Cancel", Gtk.ResponseType.CANCEL
            )

            content_area = dialog.get_content_area()
            rows_entry = Gtk.Entry()
            rows_entry.set_placeholder_text("Number of rows")
            cols_entry = Gtk.Entry()
            cols_entry.set_placeholder_text("Number of columns")
            content_area.append(rows_entry)
            content_area.append(cols_entry)

            dialog.show()

            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.OK:
                    try:
                        rows = int(rows_entry.get_text())
                        cols = int(cols_entry.get_text())
                        headers = [f"field{i + 1}" for i in range(cols)]
                        table_lines = [
                            "| " + " | ".join(headers) + " |",
                            "| " + " | ".join(["---"] * cols) + " |",
                        ]
                        for _ in range(rows):
                            table_lines.append(
                                "| "
                                + " | ".join([f"field{i + 1}" for i in range(cols)])
                                + " |"
                            )
                        buffer_iter = buffer.get_iter_at_mark(buffer.get_insert())
                        buffer.insert(buffer_iter, "\n" + "\n".join(table_lines) + "\n")
                    except ValueError:
                        pass
                dialog.destroy()

            dialog.connect("response", on_response)

        # 遍历 edit_tool_box 的按钮绑定事件
        for btn in list(self.edit_tool_box):
            if not isinstance(btn, Gtk.Button):
                continue
            if btn in (self.edit_tool_save_btn, self.edit_tool_search_btn):
                continue
            label = (btn.get_label() or "").lower()
            if label == "b":
                btn.connect("clicked", partial(lambda b, w: wrap_selection("**"), btn))
            elif label == "i":
                btn.connect("clicked", partial(lambda b, w: wrap_selection("*"), btn))
            elif label == "u":
                btn.connect("clicked", partial(lambda b, w: wrap_selection("__"), btn))
            elif label == "st":
                btn.connect("clicked", partial(lambda b, w: wrap_selection("~~"), btn))
            elif label == "ol":
                btn.connect("clicked", partial(lambda b, w: insert_list(True), btn))
            elif label == "ul":
                btn.connect("clicked", partial(lambda b, w: insert_list(False), btn))
            elif label == "l":
                btn.connect("clicked", partial(lambda b, w: insert_link(), btn))
            elif label == "tb":
                btn.connect("clicked", partial(lambda b, w: insert_table(), btn))

    def bind_global_shortcuts(self):
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_global_key_pressed)
        self.window.add_controller(controller)

    def on_global_key_pressed(self, controller, keyval, keycode, state):
        ctrl_pressed = state & Gdk.ModifierType.CONTROL_MASK

        # Ctrl + S 保存
        if ctrl_pressed and keyval == Gdk.KEY_s:
            self.on_save_markdown_clicked(None)
            return True

        # Ctrl + N 新建笔记
        if ctrl_pressed and keyval == Gdk.KEY_n:
            self.on_add_note_clicked(None)
            return True

        # Ctrl + + 新增分类
        # 注意：有些键盘 + 需要 shift，实际按键是 '=' 键
        if ctrl_pressed and (keyval == Gdk.KEY_plus or keyval == Gdk.KEY_equal):
            self.on_add_category_clicked(None)
            return True

        # Ctrl + F 打开搜索并聚焦到搜索 entry
        if ctrl_pressed and keyval == Gdk.KEY_f:
            self.show_search()  # 你的 show_search 会显示搜索栏
            self.edit_search_entry.grab_focus()  # 聚焦到搜索 entry
            return True
        return False

    def show_search(self, *args):
        self.edit_search_bar.set_reveal_child(True)
        self.edit_search_entry.grab_focus()

    def hide_search(self, *args):
        self.edit_search_bar.set_reveal_child(False)
        self.edit_search_entry.set_text("")
        self.clear_highlight()
        self.search_matches = []
        self.current_match_index = -1

    def on_save_markdown_clicked(self, button):
        title = self.edit_box_title_text.get_text().strip()
        if not title or not self.current_category:
            return  # 省略 dialog 代码

        category_path = os.path.join(GIT_DIR, self.current_category)
        os.makedirs(category_path, exist_ok=True)
        file_path = os.path.join(category_path, title)

        content = self.edit_box_markdown_text_buffer.get_text(
            self.edit_box_markdown_text_buffer.get_start_iter(),
            self.edit_box_markdown_text_buffer.get_end_iter(),
            True,
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 只刷新当前 category 的 note 列表，而不是整个 load_notes
        self.notes[self.current_category] = [
            os.path.join(GIT_DIR, self.current_category, f)
            for f in os.listdir(os.path.join(GIT_DIR, self.current_category))
        ]
        self.update_note_list(self.current_category)

        # 选中刚保存的 note
        for i, item in enumerate(self.note_liststore):
            if item.title == title:
                self.note_selection.set_selected(i)
                self.current_note = item.path
                self.update_note_content(item.path)
                break

        self.console_log(f"Saved note: {file_path}")

    def on_sync_button_clicked(self, button):
        self.on_save_markdown_clicked(None)  # 先保存当前编辑

        def git_sync():
            os.makedirs(GIT_DIR, exist_ok=True)
            # 设置远程 URL
            url = self.config["repo"]
            if self.config["user"] and self.config["token"]:
                parts = url.split("://")
                if len(parts) == 2:
                    url = f"{parts[0]}://{self.config['user']}:{self.config['token']}@{parts[1]}"

            # 1. git pull
            pull = subprocess.run(
                ["git", "-C", GIT_DIR, "pull", "--no-rebase"],
                capture_output=True,
                text=True,
            )

            # 2. 处理冲突
            if "CONFLICT" in pull.stdout or "CONFLICT" in pull.stderr:
                today = datetime.now().strftime("%Y年%m月%d日")
                for root, dirs, files in os.walk(GIT_DIR):
                    if ".git" in dirs:
                        dirs.remove(".git")
                    for f in files:
                        file_path = os.path.join(root, f)
                        with open(file_path, "r", encoding="utf-8") as fr:
                            content = fr.read()
                        if "<<<<<<<" in content:  # 存在冲突
                            new_content = []
                            for line in content.split("\n"):
                                new_content.append(line)
                                if line.startswith("<<<<<<<"):
                                    new_content.append(f"// {today} 添加了代码")
                            with open(file_path, "w", encoding="utf-8") as fw:
                                fw.write("\n".join(new_content))

                # 再次 add 所有文件
                subprocess.run(["git", "-C", GIT_DIR, "add", "."])

            # 3. 检查修改/新增文件
            subprocess.run(["git", "-C", GIT_DIR, "add", "--all"])
            status = subprocess.run(
                ["git", "-C", GIT_DIR, "status", "--porcelain"],
                capture_output=True,
                text=True,
            )
            commit_msgs = []
            for line in status.stdout.splitlines():
                code, file_path = line[:2].strip(), line[3:].strip()
                file_name = os.path.basename(file_path)
                if code in ("M", "A", "??"):
                    if code == "M":
                        commit_msgs.append(f"update {file_name}")
                    else:
                        commit_msgs.append(f"add {file_name}")

            if commit_msgs:
                commit_message = "\n".join(commit_msgs)
                subprocess.run(["git", "-C", GIT_DIR, "add", "."])
                subprocess.run(["git", "-C", GIT_DIR, "commit", "-m", commit_message])

            # 4. git push
            subprocess.run(["git", "-C", GIT_DIR, "push"])

            # 完成后刷新界面
            GLib.idle_add(self.load_notes)

        threading.Thread(target=git_sync, daemon=True).start()

    def setup_category_factory(self, factory, list_item):
        label = Gtk.Label()
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        label.set_margin_start(15)
        label.set_xalign(0.0)
        list_item.set_child(label)
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect(
            "pressed",
            lambda g, n, x, y: self.show_category_context_menu(
                list_item.get_child(),
                x,
                y,
                list_item.get_item().name,
            ),
        )
        list_item.get_child().add_controller(gesture)

    def bind_category_factory(self, factory, list_item):
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(item.name)

    def setup_note_factory(self, factory, list_item):
        label = Gtk.Label()
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        label.set_margin_start(15)
        label.set_xalign(0.0)
        list_item.set_child(label)
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect(
            "pressed",
            lambda g, n, x, y: self.show_note_context_menu(
                list_item.get_child(),
                x,
                y,
                list_item.get_item().path,
            ),
        )
        list_item.get_child().add_controller(gesture)

    def delete_category(self, category_name, popover):
        popover.popdown()
        dialog = Gtk.Dialog(
            title=f"Delete category '{category_name}'?",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Ok", Gtk.ResponseType.OK)
        content_area = dialog.get_content_area()
        label = Gtk.Label(
            label=f"All notes inside '{category_name}' will be permanently deleted."
        )
        label.set_margin_top(20)
        label.set_margin_bottom(20)
        label.set_margin_start(20)
        label.set_margin_end(20)
        content_area.append(label)

        def on_response(d, response):
            if response == Gtk.ResponseType.OK:
                category_path = os.path.join(GIT_DIR, category_name)
                try:
                    shutil.rmtree(category_path)
                    self.console_log(f"delete category: {category_name}")
                    self.load_notes()
                except Exception as e:
                    self.console_log(f"delete category failed: {e}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def rename_category(self, category_name, popover):
        popover.popdown()

        dialog = Gtk.Dialog(
            title="Rename Category",
            transient_for=self.window,
            modal=True,
        )

        dialog.add_buttons(
            "Cancel",
            Gtk.ResponseType.CANCEL,
            "Rename",
            Gtk.ResponseType.OK,
        )

        box = dialog.get_content_area()

        entry = Gtk.Entry()
        entry.set_text(category_name)

        box.append(entry)

        dialog.show()

        def on_response(d, response):
            if response == Gtk.ResponseType.OK:
                new_name = entry.get_text().strip()

                if new_name and new_name != category_name:
                    old_path = os.path.join(GIT_DIR, category_name)
                    new_path = os.path.join(GIT_DIR, new_name)

                    try:
                        os.rename(old_path, new_path)

                        self.console_log(
                            f"rename category: {category_name} -> {new_name}"
                        )

                        self.load_notes()

                    except Exception as e:
                        self.console_log(f"rename category failed: {e}")

            d.destroy()

        dialog.connect("response", on_response)

    def delete_note(self, note_path, popover):
        popover.popdown()

        note_name = os.path.basename(note_path)

        dialog = Gtk.Dialog(
            title=f"Delete note '{note_name}'?",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Ok", Gtk.ResponseType.OK)
        content_area = dialog.get_content_area()
        label = Gtk.Label(label=f"The '{note_name}' will be deleted.")
        label.set_margin_top(20)
        label.set_margin_bottom(20)
        label.set_margin_start(20)
        label.set_margin_end(20)
        content_area.append(label)

        def on_response(d, response):
            if response == Gtk.ResponseType.OK:
                try:
                    os.remove(note_path)

                    self.console_log(f"delete note: {note_name}")

                    self.load_notes()

                except Exception as e:
                    self.console_log(f"delete note failed: {e}")

            d.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def rename_note(self, note_path, popover):
        popover.popdown()

        old_name = os.path.basename(note_path)

        dialog = Gtk.Dialog(
            title="Rename Note",
            transient_for=self.window,
            modal=True,
        )

        dialog.add_buttons(
            "Cancel",
            Gtk.ResponseType.CANCEL,
            "Rename",
            Gtk.ResponseType.OK,
        )

        box = dialog.get_content_area()

        entry = Gtk.Entry()
        entry.set_text(old_name)

        box.append(entry)

        dialog.show()

        def on_response(d, response):
            if response == Gtk.ResponseType.OK:
                new_name = entry.get_text().strip()

                if new_name and new_name != old_name:
                    new_path = os.path.join(
                        os.path.dirname(note_path),
                        new_name,
                    )

                    try:
                        os.rename(note_path, new_path)

                        self.console_log(f"rename note: {old_name} -> {new_name}")

                        self.load_notes()

                    except Exception as e:
                        self.console_log(f"rename note failed: {e}")

            d.destroy()

        dialog.connect("response", on_response)

    def bind_note_factory(self, factory, list_item):
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(item.title)

    def on_category_selected_changed(self, selection, param):
        self.edit_box_title_text.set_text("")
        self.edit_box_time_text_buffer.set_text("")
        self.edit_box_markdown_text_buffer.set_text("")
        self.current_note = None
        item = selection.get_selected_item()
        if item:
            self.current_category = item.name
            self.update_note_list(item.name, self.search_entry.get_text())

    def on_note_selected_changed(self, selection, param):
        item = selection.get_selected_item()
        if item:
            self.current_note = item.path
            self.update_note_content(item.path)

    def show_category_context_menu(self, widget, x, y, category_name):
        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        popover.set_parent(widget)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        delete_btn = Gtk.Button(label="Delete Category")
        rename_btn = Gtk.Button(label="Rename Category")

        delete_btn.connect(
            "clicked", lambda b: self.delete_category(category_name, popover)
        )
        rename_btn.connect(
            "clicked", lambda b: self.rename_category(category_name, popover)
        )

        box.append(delete_btn)
        box.append(rename_btn)

        popover.set_child(box)

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1

        popover.set_pointing_to(rect)
        popover.popup()

    def show_note_context_menu(self, widget, x, y, note_path):
        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        popover.set_parent(widget)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        delete_btn = Gtk.Button(label="Delete Note")
        rename_btn = Gtk.Button(label="Rename Note")

        delete_btn.connect("clicked", lambda b: self.delete_note(note_path, popover))
        rename_btn.connect("clicked", lambda b: self.rename_note(note_path, popover))

        box.append(delete_btn)
        box.append(rename_btn)

        popover.set_child(box)

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1

        popover.set_pointing_to(rect)
        popover.popup()

    def on_markdown_changed(self, textview):
        if self._markdown_render_timeout_id is not None:
            GLib.source_remove(self._markdown_render_timeout_id)

        self._markdown_render_timeout_id = GLib.timeout_add(
            300, self._render_markdown_preview
        )

    def _render_markdown_preview(self):
        content = self.edit_box_markdown_text_buffer.get_text(
            self.edit_box_markdown_text_buffer.get_start_iter(),
            self.edit_box_markdown_text_buffer.get_end_iter(),
            True,
        )
        render_markdown(self.note_textbuffer, self.note_textview, content)
        self._markdown_render_timeout_id = None
        return False

    def on_search_changed(self, entry):
        """搜索输入变化时，高亮所有匹配"""
        text = entry.get_text()
        buffer = self.edit_box_markdown_text_buffer
        self.clear_highlight()
        self.search_matches = []
        self.current_match_index = -1

        if not text:
            return

        start_iter = buffer.get_start_iter()
        while True:
            match = start_iter.forward_search(
                text, Gtk.TextSearchFlags.CASE_INSENSITIVE, None
            )
            if not match:
                break
            match_start, match_end = match
            self.search_matches.append((match_start.copy(), match_end.copy()))
            # 添加高亮标签
            buffer.create_tag(
                "search-highlight",
                background="#ffaa00",
                foreground="#000000",
                weight=Pango.Weight.BOLD,
            )
            buffer.apply_tag_by_name("search-highlight", match_start, match_end)
            start_iter = match_end

        if self.search_matches:
            self.current_match_index = 0
            self.scroll_to_current_match()

    def scroll_to_current_match(self):
        if 0 <= self.current_match_index < len(self.search_matches):
            start, end = self.search_matches[self.current_match_index]
            self.edit_box_markdown_text.scroll_to_iter(start, 0.1, True, 0.5, 0.0)
            # 可选：设置光标到当前匹配
            buffer = self.edit_box_markdown_text_buffer
            buffer.select_range(start, end)

    def search_next(self, *args):
        if not getattr(self, "search_matches", None):
            return
        self.current_match_index += 1
        if self.current_match_index >= len(self.search_matches):
            self.current_match_index = 0
        self.scroll_to_current_match()

    def search_previous(self, *args):
        if not getattr(self, "search_matches", None):
            return
        self.current_match_index -= 1
        if self.current_match_index < 0:
            self.current_match_index = len(self.search_matches) - 1
        self.scroll_to_current_match()

    def clear_highlight(self):
        buffer = self.edit_box_markdown_text_buffer
        start, end = buffer.get_start_iter(), buffer.get_end_iter()
        buffer.remove_tag_by_name("search-highlight", start, end)


def render_markdown(buffer: Gtk.TextBuffer, textview: Gtk.TextView, text: str):
    buffer.set_text("")
    tags = {}
    style_manager = GtkSource.StyleSchemeManager.get_default()
    scheme = style_manager.get_scheme("oblivion")

    def get_tag(name, **props):
        tag = buffer.get_tag_table().lookup(name)
        if not tag:
            tag = buffer.create_tag(name, **props)
        return tag

    # Markdown 标签
    for i in range(1, 7):
        tags[f"h{i}"] = get_tag(f"h{i}", weight=700, size_points=24 - (i - 1) * 2)
    tags["bold"] = get_tag("bold", weight=700)
    tags["italic"] = get_tag("italic", style=1)
    tags["underline"] = get_tag("underline", underline=1)
    tags["strikethrough"] = get_tag("strikethrough", strikethrough=True)
    tags["list_symbol"] = get_tag("list_symbol", foreground="#ffcc00")
    tags["inline_code"] = get_tag(
        "inline_code", foreground="#d4d4d4", background="#444444"
    )
    tags["link"] = get_tag("link", foreground="#1E90FF", underline=1)

    lines = text.split("\n")
    in_code_block = False
    code_content = []
    code_block_marker = None
    code_block_language = None

    def render_inline(line):
        # 内联代码
        line = re.sub(
            r"`([^`]+)`",
            lambda m: (
                buffer.insert_with_tags(
                    buffer.get_end_iter(), m.group(1), tags["inline_code"]
                )
                or ""
            ),
            line,
        )
        # 粗体 **
        line = re.sub(
            r"\*\*([^\*]+)\*\*",
            lambda m: (
                buffer.insert_with_tags(buffer.get_end_iter(), m.group(1), tags["bold"])
                or ""
            ),
            line,
        )
        # 斜体 *
        line = re.sub(
            r"\*([^\*]+)\*",
            lambda m: (
                buffer.insert_with_tags(
                    buffer.get_end_iter(), m.group(1), tags["italic"]
                )
                or ""
            ),
            line,
        )
        # 下划线 __
        line = re.sub(
            r"__([^_]+)__",
            lambda m: (
                buffer.insert_with_tags(
                    buffer.get_end_iter(), m.group(1), tags["underline"]
                )
                or ""
            ),
            line,
        )
        # 删除线 ~~
        line = re.sub(
            r"~~([^~]+)~~",
            lambda m: (
                buffer.insert_with_tags(
                    buffer.get_end_iter(), m.group(1), tags["strikethrough"]
                )
                or ""
            ),
            line,
        )
        # 链接 [text](url)
        line = re.sub(
            r"\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]\([^)]+\)",
            lambda m: (
                buffer.insert_with_tags(buffer.get_end_iter(), m.group(1), tags["link"])
                or ""
            ),
            line,
        )

        buffer.insert(buffer.get_end_iter(), line + "\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        start_iter = buffer.get_end_iter()

        # 代码块开始
        code_start_match = re.match(r"^(`{3,})(\w+)?$", stripped)
        if code_start_match and not in_code_block:
            in_code_block = True
            code_content = []
            code_block_marker = code_start_match.group(1)
            code_block_language = code_start_match.group(2)
            i += 1
            continue

        # 代码块结束
        if in_code_block:
            if stripped == code_block_marker:
                # 插入 GtkSourceView
                anchor = buffer.create_child_anchor(buffer.get_end_iter())
                scrolled_window = Gtk.ScrolledWindow()
                scrolled_window.set_hexpand(True)
                scrolled_window.set_vexpand(
                    False
                )  # 不垂直扩展，让代码块根据内容调整高度
                scrolled_window.set_propagate_natural_height(True)  # 根据内容调整高度
                scrolled_window.set_max_content_height(400)  # 设置最大高度
                scrolled_window.set_min_content_height(400)  # 设置最小高度
                scrolled_window.set_min_content_width(600)  # 设置最小高度
                scrolled_window.set_has_frame(True)  # 添加边框
                scrolled_window.set_margin_top(5)
                scrolled_window.set_margin_bottom(5)
                lang_manager = GtkSource.LanguageManager.get_default()
                source_buffer = GtkSource.Buffer()
                if code_block_language:
                    language = lang_manager.get_language(code_block_language)
                    if language:
                        source_buffer.set_language(language)
                if scheme:
                    source_buffer.set_style_scheme(scheme)
                source_buffer.set_text("\n".join(code_content))
                source_view = GtkSource.View.new_with_buffer(source_buffer)
                source_view.set_monospace(True)
                source_view.set_show_line_numbers(True)
                source_view.set_hexpand(True)
                source_view.set_vexpand(True)  # 让视图在 ScrolledWindow 中扩展
                source_view.set_editable(False)  # 预览模式不可编辑
                source_view.set_wrap_mode(Gtk.WrapMode.NONE)  # 代码块不换行
                source_view.show()
                scrolled_window.set_child(source_view)
                scrolled_window.show()
                textview.add_child_at_anchor(scrolled_window, anchor)
                buffer.insert(buffer.get_end_iter(), "\n")
                in_code_block = False
                code_content = []
                code_block_marker = None
                code_block_language = None
                i += 1
                continue
            else:
                code_content.append(line)
                i += 1
                continue

        # 分割线
        if re.match(r"^([-*_]{3,})$", stripped):
            anchor = buffer.create_child_anchor(start_iter)
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.show()
            textview.add_child_at_anchor(separator, anchor)
            buffer.insert(buffer.get_end_iter(), "\n")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            buffer.insert_with_tags(start_iter, m.group(2) + "\n", tags[f"h{level}"])
            i += 1
            continue

        # 块引用
        m = re.match(r"^>\s?(.*)$", stripped)
        if m:
            content = m.group(1)
            anchor = buffer.create_child_anchor(start_iter)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_margin_start(20)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            label = Gtk.Label(label=content)
            label.set_xalign(0)
            label.set_wrap(True)
            box.append(label)
            box.show()
            textview.add_child_at_anchor(box, anchor)
            buffer.insert(buffer.get_end_iter(), "\n")
            i += 1
            continue

        # 有序列表
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            buffer.insert_with_tags(start_iter, m.group(1) + ". ", tags["list_symbol"])
            render_inline(m.group(2))
            i += 1
            continue

        # 无序列表
        m = re.match(r"^([-+*])\s+(.*)$", stripped)
        if m:
            buffer.insert_with_tags(start_iter, "• ", tags["list_symbol"])
            render_inline(m.group(2))
            i += 1
            continue

        # 普通文本
        render_inline(line)
        i += 1


def on_textview_click(gesture, n_press, x, y, link_ranges):
    textview = gesture.get_widget()
    iter_ = textview.get_iter_at_location(int(x), int(y))
    offset = iter_.get_offset()
    for (start, end), url in link_ranges.items():
        if start <= offset < end:
            import webbrowser

            webbrowser.open(url)
            break


if __name__ == "__main__":
    app = NoteApp()
    app.run()
