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
        # 弹窗输入分类名
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
        self.window.set_title("Notebook App")
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", True
        )

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_hexpand(True)
        toolbar.set_vexpand(False)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_valign(Gtk.Align.FILL)
        self.search_entry.set_width_chars(50)  # 固定宽度大约200px
        self.search_entry.connect("activate", self.on_search_icon_activated)
        toolbar.append(self.search_entry)

        # 设置按钮固定右侧
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

        # category_column
        cat_column = Gtk.TreeViewColumn("Category", Gtk.CellRendererText(), text=0)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        label = Gtk.Label(label="Category")
        header_box.append(label)

        cate_add_btn = Gtk.Button(label="+")
        cate_add_btn.set_valign(Gtk.Align.CENTER)
        cate_add_btn.connect("clicked", self.on_settings_clicked)
        cate_add_btn.get_style_context().add_class("cate-button")
        cate_add_btn_spacer = Gtk.Box()
        cate_add_btn_spacer.set_hexpand(True)
        header_box.append(cate_add_btn_spacer)
        header_box.append(cate_add_btn)
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

        note_column = Gtk.TreeViewColumn("Note", Gtk.CellRendererText(), text=0)
        note_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        note_label = Gtk.Label(label="Note")
        note_header_box.append(note_label)
        note_add_btn = Gtk.Button(label="+")
        note_add_btn.set_valign(Gtk.Align.CENTER)
        note_add_btn.connect("clicked", self.on_settings_clicked)
        note_add_btn.get_style_context().add_class("flat-button")
        note_add_btn_spacer = Gtk.Box()
        note_add_btn_spacer.set_hexpand(True)
        note_header_box.append(note_add_btn_spacer)
        note_header_box.append(note_add_btn)
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
        note_scrolled_view.set_margin_top(45)
        note_scrolled_view.set_margin_bottom(45)
        note_scrolled_view.set_margin_start(45)
        note_scrolled_view.set_margin_end(45)
        note_scrolled_view.get_style_context().add_class("note-area")
        note_textview.set_name("note-textview")

        # Horizontal Paned 左中右
        middle_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        middle_pane.set_start_child(note_scrolled)
        middle_pane.set_end_child(note_scrolled_view)
        middle_pane.set_position(300)
        middle_pane.get_style_context().add_class("middle-pane")
        main_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        main_pane.set_start_child(category_scrolled)
        main_pane.set_end_child(middle_pane)
        main_pane.set_position(250)

        # CSS 扁平化
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .flat-button {
            border-radius:0;
            border-width:0;
            box-shadow:none;
            background-color:#3c3c3c;
            color:#ffffff;
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
        .middle-pane {
            background-color:#1e1e1e;
        }

        .note-area {
            background-color:#1e1e1e;
        }
        .note-area > viewport {
            background-color: #1e1e1e;
        }
        #note-textview {
            background-color: transparent;
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

        self.window.set_child(vbox)
        self.load_notes()
        self.window.show()


if __name__ == "__main__":
    app = NoteApp()
    app.run()
