#!/usr/bin/env python3
import json
import os
import subprocess
import threading
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

HOME_DIR = os.path.expanduser("~")
APP_DIR = os.path.join(HOME_DIR, ".local/.books")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
GIT_DIR = os.path.join(APP_DIR, "git")


class NoteApp(Gtk.Application):
    def __init__(self):
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
                dirs.remove(".git")  # 隐藏.git
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
        self.category_store.clear()
        for cat in self.categories:
            if search and search.lower() not in cat.lower():
                continue
            self.category_store.append([cat])
        first_iter = self.category_store.get_iter_first()
        if first_iter:
            self.category_tree.get_selection().select_iter(first_iter)

    def update_note_list(self, category, search=None):
        self.note_store.clear()
        for note_file in self.notes.get(category, []):
            title = os.path.basename(note_file)
            if search and search.lower() not in title.lower():
                continue
            self.note_store.append([title, note_file])
        first_iter = self.note_store.get_iter_first()
        if first_iter:
            self.note_tree.get_selection().select_iter(first_iter)

    def update_note_content(self, note_file):
        if not os.path.exists(note_file):
            self.note_textbuffer.set_text("")
            return
        with open(note_file, "r") as f:
            content = f.read()
        stats = os.stat(note_file)
        created = datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        display_text = (
            f"Created: {created}\nTitle: {os.path.basename(note_file)}\n\n{content}"
        )
        self.note_textbuffer.set_text(display_text)

    def on_category_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            category = model[treeiter][0]
            self.current_category = category
            self.update_note_list(category, self.search_entry.get_text())

    def on_note_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            note_file = model[treeiter][1]
            self.current_note = note_file
            self.update_note_content(note_file)

    def on_search_icon_activated(self, search_entry):
        search_text = search_entry.get_text()
        self.update_category_list(search_text)
        if self.current_category:
            self.update_note_list(self.current_category, search_text)
            first_iter = self.note_store.get_iter_first()
            if first_iter:
                note_file = self.note_store[first_iter][1]
                self.current_note = note_file
                self.update_note_content(note_file)

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

        # Labels
        grid.attach(Gtk.Label(label="Git Repo URL", halign=Gtk.Align.END), 0, 0, 1, 1)
        grid.attach(Gtk.Label(label="User / OAuth2", halign=Gtk.Align.END), 0, 1, 1, 1)
        grid.attach(
            Gtk.Label(label="Token / Personal Token", halign=Gtk.Align.END), 0, 2, 1, 1
        )

        # Entries
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
        pass  # 后续实现

    def show_message(self, text):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.show()
        dialog.connect("response", lambda d, r: d.destroy())

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

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toolbar.set_hexpand(True)
        toolbar.get_style_context().add_class("toolbar")

        # Entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search...")
        self.search_entry.set_width_chars(20)
        toolbar.append(self.search_entry)

        # 搜索按钮
        self.search_button = Gtk.Button()
        toolbar.append(self.search_button)
        # search button logo
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
        # sync_button.connect("clicked", self.on_sync_clicked)
        toolbar.append(sync_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.get_style_context().add_class("toolbar-separator")
        toolbar.append(separator)

        # settings button
        settings_button = Gtk.Button(label="⚙")
        settings_button.set_valign(Gtk.Align.CENTER)
        settings_button.connect("clicked", self.on_settings_clicked)
        settings_button.get_style_context().add_class("flat-button")
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)
        toolbar.append(settings_button)

        # Left: Category
        self.category_store = Gtk.ListStore(str)
        self.category_tree = Gtk.TreeView(model=self.category_store)
        self.category_tree.get_selection().connect("changed", self.on_category_selected)
        renderer = Gtk.CellRendererText()
        renderer.set_property("height", 30)  # 设置行高
        renderer.set_padding(5, 5)  # 上下 padding

        # category_column
        cat_column = Gtk.TreeViewColumn("Category", renderer, text=0)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        label = Gtk.Label(label="Category +")
        header_box.append(label)
        cat_column.set_widget(header_box)
        cat_column.connect("clicked", lambda col: self.on_add_category_clicked(None))
        self.category_tree.append_column(cat_column)

        category_scrolled = Gtk.ScrolledWindow()
        category_scrolled.set_child(self.category_tree)
        category_scrolled.set_vexpand(True)

        # Middle: Note
        self.note_store = Gtk.ListStore(str, str)
        self.note_tree = Gtk.TreeView(model=self.note_store)
        self.note_tree.get_selection().connect("changed", self.on_note_selected)

        note_column = Gtk.TreeViewColumn("Note", renderer, text=0)
        note_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        note_label = Gtk.Label(label="Note +")
        note_header_box.append(note_label)
        note_column.set_widget(note_header_box)
        self.note_tree.append_column(note_column)

        note_scrolled = Gtk.ScrolledWindow()
        note_scrolled.set_child(self.note_tree)
        note_scrolled.set_vexpand(True)

        # Right: content
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

        # Horizontal Paned 左中右
        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        edit_box.set_hexpand(True)
        edit_box.set_vexpand(True)
        # ---- 标题编辑 ----
        title_buffer = Gtk.TextBuffer()
        title_view = Gtk.TextView(buffer=title_buffer)
        title_view.set_wrap_mode(Gtk.WrapMode.NONE)
        title_view.set_vexpand(False)
        title_view.set_size_request(-1, 40)
        edit_box.append(title_view)
        # ---- 时间显示（只读）----
        from datetime import datetime

        time_buffer = Gtk.TextBuffer()
        time_buffer.set_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time_view = Gtk.TextView(buffer=time_buffer)
        time_view.set_editable(False)
        time_view.set_cursor_visible(False)
        time_view.set_wrap_mode(Gtk.WrapMode.NONE)
        time_view.set_vexpand(False)
        time_view.set_size_request(-1, 30)
        edit_box.append(time_view)
        markdown_buffer = Gtk.TextBuffer()
        markdown_view = Gtk.TextView(buffer=markdown_buffer)
        markdown_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        markdown_view.set_hexpand(True)
        markdown_view.set_vexpand(True)
        markdown_scrolled = Gtk.ScrolledWindow()
        markdown_scrolled.set_child(markdown_view)
        markdown_scrolled.set_hexpand(True)
        markdown_scrolled.set_vexpand(True)
        edit_box.append(markdown_scrolled)
        edit_area = edit_box

        # 右侧：edit_area + note_scrolled_view
        right_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        right_pane.set_start_child(edit_area)
        right_pane.set_end_child(note_scrolled_view)
        right_pane.set_position(500)

        # 中间：note titles + 右侧整体
        middle_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        middle_pane.set_start_child(note_scrolled)
        middle_pane.set_end_child(right_pane)
        middle_pane.set_position(300)

        # 最左：category + 其他
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
            background-color: #1e1e1e;
            border-bottom:1px solid black;
        }
        entry {
            border: none;
            border-radius: 0;
            background-color: #1e1e1e;
            color: #ffffff;
            padding: 4px;
            padding-left:10px;
            padding-right:10px;
            outline: none;
        }
        entry:focus {
            background-color: #1e1e1e;
            -GtkEntry-focus-line-width: 1px;
            -GtkEntry-focus-border: #000000;
            box-shadow: none;
        }
        entry:backdrop {
            background-color: #1e1e1e;
        }
        button {
            border: none;
            background-image: none;
            background-color: #1e1e1e;
            border-radius: 0;
        }
        button:hover {
            background-color: #1e1e1e;
        }
        button:active {
            background-color: #1e1e1e;
        }
        image {
            color: #c1c1c1;
        }
        button:hover image {
            color: #ffffff;
        }

        treeview.view {
            row-height: 30px;
        }
        treeview.view header button {
            min-height: 30px;
            padding-top: 5px;
            padding-bottom: 5px;
        }

        .toolbar-separator {
            background-color: black;
            padding: 0;
            margin: 0;
        }
        .sync-button {
            background-color: #1e1e1e;
            border: none;
            border-radius: 0;
            padding: 4px 24px;
            margin: 0;
        }
        .sync-button:hover {
            background-color: #1e1e1e;
        }
        .sync-button:active {
            background-color: #1e1e1e;
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
            background-color: #1e1e1e;
            border-radius: 0;
            color: #c1c1c1;
        }
        .flat-button:hover {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        .cate-button {
            border-radius:0;
            border-width:0;
            box-shadow:none;
            background-color:#2d2d2d;
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
            background-color:#1e1e1e;
        }

        .note-area {
            background-color:#1e1e1e;
        }
        .note-area > viewport {
            background-color: #1e1e1e;
        }
        #note-textview {
            background-color: #1e1e1e;
        }

        .console-area {
            padding: 20px;
            color: #1bd66c;
            background-color: #1e1e1e;
            border-top:1px solid black;
            font-size: 13px;
            caret-color: #1bd66c;
        }
        .console-area:selected {
            background-color: #4a90e2;
            color: #ffffff;
        }
        .console-area textview {
            background-color: #1e1e1e;
            color: #1bd66c;
            font-family: monospace;
            font-size: 13px;
        }
        .console-area textview text {
            background-color: #1e1e1e;
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


if __name__ == "__main__":
    app = NoteApp()
    app.run()
