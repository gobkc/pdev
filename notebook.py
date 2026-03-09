#!/usr/bin/env python3
import json
import os
import re
import subprocess
import threading
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

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
            if search and search.lower() not in title.lower():
                continue
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
        render_markdown(self.note_textbuffer, content)
        stats = os.stat(note_file)
        created = datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        # display_text = (
        #     f"Title: {os.path.basename(note_file)}\nCreated: {created}\n\n{content}"
        # )
        # self.note_textbuffer.set_text(display_text)
        self.edit_box_title_text.set_text(os.path.basename(note_file))
        self.edit_box_time_text_buffer.set_text(created)
        self.edit_box_markdown_text.set_text(content)

    def on_search_icon_activated(self, search_entry):
        search_text = search_entry.get_text()
        self.update_category_list(search_text)
        if self.current_category:
            self.update_note_list(self.current_category, search_text)

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

    def on_activate(self, app):
        self.load_config()
        self.clone_or_pull_repo()
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(1200, 800)
        self.window.maximize()
        self.window.set_title("Git Notebook")
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
        label = Gtk.Label(label="Sync Notebook")
        label.get_style_context().add_class("sync-label")
        button_content.append(label)
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
        # note_add_btn.connect("clicked", self.on_add_note_clicked)
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
        note_textview = Gtk.TextView(buffer=self.note_textbuffer)
        note_textview.set_editable(False)
        note_scrolled_view = Gtk.ScrolledWindow()
        note_scrolled_view.set_child(note_textview)
        note_scrolled_view.set_vexpand(True)
        note_textview.set_left_margin(35)
        note_textview.set_right_margin(35)
        note_textview.set_top_margin(35)
        note_textview.set_bottom_margin(35)
        note_scrolled_view.get_style_context().add_class("note-area")
        note_textview.set_name("note-textview")
        # click = Gtk.GestureClick()
        # click.connect("pressed", on_textview_click, link_ranges)
        # textview.add_controller(click)

        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        edit_box.set_hexpand(True)
        edit_box.set_vexpand(True)
        edit_box_titilebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        edit_box_titilebar.set_hexpand(True)
        edit_box_titilebar.set_name("titlebar")
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
        edit_box_time_text.set_left_margin(30)
        edit_box_time_text.set_right_margin(15)
        edit_box_time_text.set_size_request(179, 20)
        edit_box_time_text.set_name("time-text")
        edit_box_time_text.set_halign(Gtk.Align.END)
        edit_box_titilebar.append(edit_box_time_text)
        edit_box.append(edit_box_titilebar)
        self.edit_box_markdown_text = Gtk.TextBuffer()
        edit_box_markdown_text = Gtk.TextView(buffer=self.edit_box_markdown_text)
        edit_box_markdown_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        edit_box_markdown_text.set_hexpand(True)
        edit_box_markdown_text.set_vexpand(True)
        edit_box_markdown_text.set_left_margin(35)
        edit_box_markdown_text.set_right_margin(35)
        edit_box_markdown_text.set_top_margin(35)
        edit_box_markdown_text.set_bottom_margin(35)
        edit_box_markdown_text.set_name("markdown-text")
        self.edit_box_markdown_text.connect("changed", self.on_markdown_changed)
        markdown_scrolled = Gtk.ScrolledWindow()
        markdown_scrolled.set_child(edit_box_markdown_text)
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

        self.console_log = console_log

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
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
        #title-text{
            padding-left:15px;
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

    def setup_category_factory(self, factory, list_item):
        label = Gtk.Label()
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        label.set_margin_start(15)
        label.set_xalign(0.0)
        list_item.set_child(label)

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

    def bind_note_factory(self, factory, list_item):
        item = list_item.get_item()
        label = list_item.get_child()
        label.set_text(item.title)

    def on_category_selected_changed(self, selection, param):
        item = selection.get_selected_item()
        if item:
            self.current_category = item.name
            self.update_note_list(item.name, self.search_entry.get_text())

    def on_note_selected_changed(self, selection, param):
        item = selection.get_selected_item()
        if item:
            self.current_note = item.path
            self.update_note_content(item.path)

    def on_markdown_changed(self, textview):
        if self._markdown_render_timeout_id is not None:
            GLib.source_remove(self._markdown_render_timeout_id)

        self._markdown_render_timeout_id = GLib.timeout_add(
            300, self._render_markdown_preview
        )

    def _render_markdown_preview(self):
        content = self.edit_box_markdown_text.get_text(
            self.edit_box_markdown_text.get_start_iter(),
            self.edit_box_markdown_text.get_end_iter(),
            True,
        )
        render_markdown(self.note_textbuffer, content)
        self._markdown_render_timeout_id = None
        return False


def render_markdown(buffer, text):
    import re

    buffer.set_text("")
    tags = {}

    def get_tag(name, **props):
        tag = buffer.get_tag_table().lookup(name)
        if not tag:
            tag = buffer.create_tag(name, **props)
        return tag

    for i in range(1, 7):
        tags[f"h{i}"] = get_tag(f"h{i}", weight=700, size_points=24 - (i - 1) * 2)
    tags["bold"] = get_tag("bold", weight=700)
    tags["italic"] = get_tag("italic", style=1)
    tags["bolditalic"] = get_tag("bolditalic", weight=700, style=1)
    tags["underline"] = get_tag("underline", underline=1)
    tags["strikethrough"] = get_tag("strikethrough", strikethrough=True)
    tags["quote"] = get_tag(
        "quote", background="#2b2b2b", left_margin=20, foreground="#888888"
    )
    tags["list_symbol"] = get_tag("list_symbol", foreground="#ffcc00")
    tags["list"] = get_tag("list", left_margin=20)
    tags["code"] = get_tag(
        "code",
        family="Monospace",
        foreground="#d4d4d4",
        background="#b3f0d8",
        pixels_above_lines=2,
        pixels_below_lines=2,
        left_margin=0,
        right_margin=0,
    )
    tags["code_keyword"] = get_tag("code_keyword", foreground="#569CD6", weight=700)
    tags["code_func"] = get_tag("code_func", foreground="#DCDCAA")
    tags["inline_code"] = get_tag(
        "inline_code", foreground="#d4d4d4", background="#444444"
    )
    tags["link"] = get_tag("link", foreground="#1E90FF", underline=1)
    tags["hr"] = get_tag("hr", foreground="#888888")

    lines = text.split("\n")
    in_code_block = False
    code_content = []

    def render_inline(line):
        pos = buffer.get_end_iter()

        def replace_inline_code(m):
            buffer.insert_with_tags(
                buffer.get_end_iter(), m.group(1), tags["inline_code"]
            )
            return ""

        line = re.sub(r"`([^`]+)`", replace_inline_code, line)
        line = re.sub(
            r"\*\*([^\*]+)\*\*",
            lambda m: (
                buffer.insert_with_tags(buffer.get_end_iter(), m.group(1), tags["bold"])
                or ""
            ),
            line,
        )
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

        def link_repl(m):
            buffer.insert_with_tags(buffer.get_end_iter(), m.group(1), tags["link"])
            return ""

        pattern = r"\[([^\]]+(\[[^\]]*\])*)\]\([^)]+\)"
        line = re.sub(pattern, link_repl, line)
        buffer.insert_with_tags(buffer.get_end_iter(), line + "\n")

    for line in lines:
        stripped = line.lstrip()
        start_iter = buffer.get_end_iter()
        if re.match(r"^([-*_]{3,})$", stripped) or stripped == "---":
            buffer.insert_with_tags(buffer.get_end_iter(), "─" * 100 + "\n", tags["hr"])
            continue
        if re.match(r"^(#{1,6})\s+(.*)$", stripped):
            level = len(re.match(r"^(#{1,6})\s+", stripped).group(1))
            buffer.insert_with_tags(
                start_iter, stripped[level + 1 :] + "\n", tags[f"h{level}"]
            )
            continue
        if re.match(r"^>\s?(.*)$", stripped):
            buffer.insert_with_tags(start_iter, stripped[1:] + "\n", tags["quote"])
            continue
        if re.match(r"^(\d+)\.\s+(.*)$", stripped):
            m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
            buffer.insert_with_tags(start_iter, m.group(1) + ". ", tags["list_symbol"])
            render_inline(m.group(2))
            continue
        if re.match(r"^([-+*])\s+(.*)$", stripped):
            buffer.insert_with_tags(start_iter, "• ", tags["list_symbol"])
            render_inline(re.match(r"^([-+*])\s+(.*)$", stripped).group(2))
            continue
            if line.startswith("```") or (
                line.startswith("    ") and not in_code_block
            ):
                in_code_block = True
                code_content = []
                continue
            if in_code_block:
                if line.startswith("```") or line == "":
                    in_code_block = False
                    for code_line in code_content:
                        start_iter = buffer.get_end_iter()
                        buffer.insert_with_tags(
                            start_iter, code_line + "\n", tags["code"]
                        )
                        # 关键字高亮
                        for w in re.finditer(
                            r"\b(def|return|for|if|else|while|import|class|package|func|var|type)\b",
                            code_line,
                        ):
                            buffer.apply_tag(
                                tags["code_keyword"],
                                buffer.get_iter_at_offset(
                                    start_iter.get_offset() + w.start()
                                ),
                                buffer.get_iter_at_offset(
                                    start_iter.get_offset() + w.end()
                                ),
                            )
                        # 函数名高亮
                        for f in re.finditer(r"\b([a-zA-Z_]\w*)\s*(?=\()", code_line):
                            buffer.apply_tag(
                                tags["code_func"],
                                buffer.get_iter_at_offset(
                                    start_iter.get_offset() + f.start()
                                ),
                                buffer.get_iter_at_offset(
                                    start_iter.get_offset() + f.end()
                                ),
                            )
                    continue
                code_content.append(line)  # 保留所有空格，不 lstrip
                continue
        render_inline(stripped)


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
