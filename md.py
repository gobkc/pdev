import os
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import markdown
from weasyprint import HTML


class DarkMarkdownEditor(tk.Tk):
    def __init__(self, initial_file=None):
        super().__init__()
        self.title("Markdown Editor")
        self.geometry("1200x700")
        self.update_idletasks()
        self.attributes("-zoomed", True)
        self.configure(bg="#26282b")
        self.current_file = None
        self.current_folder = None
        self._build_ui()
        self._bind_shortcuts()
        if initial_file and os.path.isfile(initial_file):
            self.panedwindow.forget(self.left)
            self.load_file_async(initial_file)

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#26282b",
            foreground="#b0b1b3",
            fieldbackground="#26282b",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            highlightbackground="#26282b",
            highlightcolor="#26282b",
        )
        style.map(
            "Treeview",
            background=[("selected", "#26282b")],
            foreground=[("selected", "#70b877")],
            highlightcolor=[("focus", "#26282b")],
            highlightbackground=[("focus", "#26282b")],
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#3d3e41",
            troughcolor="#191a1c",
            arrowcolor="#191a1c",
            borderwidth=0,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", "#5c5e60")],
            troughcolor=[("active", "#191a1c")],
            arrowcolor=[("active", "#191a1c")],
        )
        toolbar = tk.Frame(self, bg="#26282b", borderwidth=0)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        for text, cmd, shortcut, icon in [
            ("New", self.new_file, "Ctrl+N", "📝"),
            ("Open Folder", self.open_folder, "Ctrl+Shift+O", "📂"),
            ("Open", self.open_file, "Ctrl+O", "📄"),
            ("Save", self.save_file, "Ctrl+S", "💾"),
            ("Export PDF", self.export_pdf, "Ctrl+P", "📜"),
        ]:
            btn = tk.Button(
                toolbar,
                text=f"{icon} {text} ({shortcut})",
                bg="#191a1c",
                fg="#b0b1b3",
                relief=tk.FLAT,
                activebackground="#191a1c",
                activeforeground="#b0b1b3",
                highlightbackground="#191a1c",
                highlightcolor="#191a1c",
                anchor="w",
                font=("Consolas", 11),
                padx=8,
                pady=4,
                command=cmd,
            )
            btn.pack(side=tk.LEFT, padx=4, pady=2)
            self._add_button_hover(btn)

        self.panedwindow = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=4, bg="#26282b"
        )
        self.panedwindow.pack(fill=tk.BOTH, expand=True)

        # ---- 左侧 Treeview 区 ----
        self.left = tk.Frame(self.panedwindow, width=0, bg="#26282b", borderwidth=0)

        # 内部容器，用于 Treeview + 滚动条
        tree_container = tk.Frame(self.left, bg="#26282b")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_container, show="tree", takefocus=0)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.open_from_tree)
        self.tree.bind("<Button-3>", self.show_tree_context_menu)

        self.tree_scroll = ttk.Scrollbar(
            tree_container, command=self.tree.yview, style="Vertical.TScrollbar"
        )
        self.tree["yscrollcommand"] = self.tree_scroll.set
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview 右键菜单
        self.tree_menu = tk.Menu(
            self,
            tearoff=0,
            bg="#26282b",
            fg="#dcdcdc",
            activebackground="#191a1c",
            activeforeground="#70b877",
            font=("Consolas", 11),
        )
        self.tree_menu.add_command(label="Rename", command=self.rename_tree_item)
        self.tree_menu.add_command(label="Delete", command=self.delete_item)

        self.panedwindow.add(self.left)

        center = tk.Frame(self.panedwindow, bg="#191a1c")
        self.editor = tk.Text(
            center,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg="#191a1c",
            fg="#dcdcdc",
            insertbackground="white",
            selectbackground="#555555",
            undo=True,
            borderwidth=0,
            relief=tk.SOLID,
            highlightbackground="#191a1c",
            highlightcolor="#191a1c",
            padx=15,
            pady=15,
        )
        self.editor.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.editor.bind("<KeyRelease>", self.on_edit)
        self._bind_editor_shortcuts()
        self.editor.tag_configure("header", foreground="#1f4fd8")
        self.editor.tag_configure("bold", font=("Consolas", 11, "bold"))
        self.editor.tag_configure("italic", font=("Consolas", 11, "italic"))
        self.editor.tag_configure("list", foreground="#50fa7b")
        self.editor.tag_configure("code", foreground="#0a7acc", background="#2d2d2d")
        self.editor_scroll = ttk.Scrollbar(
            center, command=self.editor.yview, style="Vertical.TScrollbar"
        )
        self.editor["yscrollcommand"] = self.editor_scroll.set
        self.editor_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.panedwindow.add(center)

        right = tk.Frame(self.panedwindow, bg="#191a1c")
        self.preview = tk.Text(
            right,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg="#191a1c",
            fg="#dcdcdc",
            insertbackground="white",
            selectbackground="#555555",
            borderwidth=0,
            relief=tk.SOLID,
            highlightbackground="#191a1c",
            highlightcolor="#191a1c",
            padx=15,
            pady=15,
        )
        self.preview.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.preview_scroll = ttk.Scrollbar(
            right, command=self.preview.yview, style="Vertical.TScrollbar"
        )
        self.preview["yscrollcommand"] = self.preview_scroll.set
        self.preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._configure_preview_tags()
        self.panedwindow.add(right)
        self._bind_preview_links()

    def _configure_preview_tags(self):
        self.preview.tag_configure("header", foreground="#1f4fd8")
        for i in range(1, 7):
            self.preview.tag_configure(
                f"h{i}", font=("Consolas", 40 - (i - 1) * 5, "bold")
            )
        self.preview.tag_configure("bold", font=("Consolas", 11, "bold"))
        self.preview.tag_configure("italic", font=("Consolas", 11, "italic"))
        self.preview.tag_configure("list", foreground="#50fa7b")
        self.preview.tag_configure("link", foreground="#8be9fd", underline=True)
        self.preview.tag_configure("code", foreground="#0a7acc", background="#2d2d2d")
        self.preview.tag_configure(
            "blockquote", foreground="#6272a4", font=("Consolas", 11, "italic")
        )
        self.preview.tag_configure("table", foreground="#f8f8f2", background="#2d2d2d")
        self.preview.tag_configure("th", foreground="#50fa7b", background="#000000")
        self.preview.tag_configure("td", foreground="#f8f8f2", background="#2d2d2d")
        self.preview.tag_configure("hr", foreground="#dcdcdc", underline=False)

    def _add_button_hover(self, btn):
        btn.bind("<Enter>", lambda e: btn.config(bg="#191a1c"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#191a1c"))

    def _bind_shortcuts(self):
        self.bind("<Control-n>", lambda e: (self.new_file(), "break"))
        self.bind("<Control-o>", lambda e: (self.open_file(), "break"))
        self.bind("<Control-s>", lambda e: (self.save_file(), "break"))
        self.bind("<Control-Shift-O>", lambda e: (self.open_folder(), "break"))
        self.bind("<Control-p>", lambda e: (self.export_pdf(), "break"))

    def _bind_editor_shortcuts(self):
        self.editor.bind(
            "<Control-a>", lambda e: self.editor.tag_add("sel", "1.0", "end") or "break"
        )
        self.editor.bind(
            "<Control-x>", lambda e: self.editor.event_generate("<<Cut>>") or "break"
        )
        self.editor.bind(
            "<Control-c>", lambda e: self.editor.event_generate("<<Copy>>") or "break"
        )
        self.editor.bind(
            "<Control-v>", lambda e: self.editor.event_generate("<<Paste>>") or "break"
        )
        self.editor.bind("<Control-z>", lambda e: self.editor.edit_undo() or "break")
        self.editor.bind("<Control-y>", lambda e: self.editor.edit_redo() or "break")
        self.editor.bind(
            "<Tab>", lambda e: self.editor.insert("insert", "    ") or "break"
        )
        self.editor.bind("<Shift-Tab>", lambda e: self._shift_tab())

    def _shift_tab(self):
        index = self.editor.index("insert linestart")
        line = self.editor.get(index, f"{index} lineend")
        if line.startswith("    "):
            self.editor.delete(index, f"{index}+4c")
        elif line.startswith("\t"):
            self.editor.delete(index, f"{index}+1c")
        return "break"

    def new_file(self):
        folder = self.current_folder or os.path.expanduser("~")
        filename = tk.simpledialog.askstring(
            "New File", "Enter new markdown file name:"
        )
        if filename:
            if not filename.endswith(".md"):
                filename += ".md"
            path = os.path.join(folder, filename)
            if os.path.exists(path):
                messagebox.showerror("Error", "File already exists!")
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write("")  # 创建空白文件
            self.current_folder = folder
            self._list_markdown_files(folder)

            # 自动选中并滚动到新建文件
            for item in self.tree.get_children():
                if self.tree.item(item, "values")[0] == path:
                    self.tree.selection_set(item)
                    self.tree.see(item)
                    break

            self.load_file_async(path)

    def show_tree_context_menu(self, event):
        selected_item = self.tree.identify_row(event.y)
        if selected_item:
            self.tree.selection_set(selected_item)
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def rename_tree_item(self):
        item = self.tree.selection()
        if not item:
            return
        old_path = self.tree.item(item[0], "values")[0]
        folder = os.path.dirname(old_path)
        new_name = tk.simpledialog.askstring(
            "Rename File",
            "Enter new file name:",
            initialvalue=os.path.basename(old_path),
        )
        if new_name:
            if not new_name.endswith(".md"):
                new_name += ".md"
            new_path = os.path.join(folder, new_name)
            if os.path.exists(new_path):
                messagebox.showerror("Error", "File already exists!")
                return
            os.rename(old_path, new_path)
            self._list_markdown_files(folder)

            # 自动选中并滚动到新文件
            for item_id in self.tree.get_children():
                if self.tree.item(item_id, "values")[0] == new_path:
                    self.tree.selection_set(item_id)
                    self.tree.see(item_id)
                    break

            self.load_file_async(new_path)

    def delete_item(self):
        item = self.tree.selection()
        if not item:
            return
        file_path = self.tree.item(item[0], "values")[0]

        confirm = messagebox.askyesno(
            "Delete File",
            f"Are you sure you want to delete:\n{os.path.basename(file_path)}?",
        )
        if not confirm:
            return

        try:
            os.remove(file_path)
            folder = os.path.dirname(file_path)
            self._list_markdown_files(folder)

            if self.current_file == file_path:
                self.current_file = None
                self.editor.delete("1.0", tk.END)
                self.preview.delete("1.0", tk.END)
                self.current_folder = folder

            messagebox.showinfo(
                "Deleted", f"File deleted:\n{os.path.basename(file_path)}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete file:\n{e}")

    def open_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.current_folder = path
            self._list_markdown_files(path)

    def _list_markdown_files(self, folder_path):
        self.tree.delete(*self.tree.get_children())
        md_files = [f for f in sorted(os.listdir(folder_path)) if f.endswith(".md")]
        print(f"DEBUG: folder={folder_path}, md_files={md_files}")  # <--- 调试用
        for filename in md_files:
            full_path = os.path.join(folder_path, filename)
            self.tree.insert("", "end", text=filename, values=[full_path])
        if md_files:
            self.panedwindow.paneconfig(self.left, width=220)
        else:
            self.panedwindow.paneconfig(self.left, width=0, minsize=0)

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")]
        )
        if path:
            folder = os.path.dirname(path)
            self.current_folder = folder
            self._list_markdown_files(folder)
            self.load_file_async(path)

    def open_from_tree(self, event):
        item = self.tree.selection()
        if item:
            path = self.tree.item(item[0], "values")[0]
            if os.path.isfile(path) and path.endswith(".md"):
                self.load_file_async(path)

    def load_file_async(self, path):
        def task():
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.after(0, lambda: self._update_editor_preview(content, path))

        threading.Thread(target=task, daemon=True).start()

    def _update_editor_preview(self, content, path):
        self.editor.delete("1.0", tk.END)
        self.editor.insert(tk.END, content)
        self.current_file = path
        self._apply_editor_highlight()
        self.update_preview()

    def save_file(self):
        if not self.current_file:
            path = filedialog.asksaveasfilename(defaultextension=".md")
            if not path:
                return
            self.current_file = path
        with open(self.current_file, "w", encoding="utf-8") as f:
            f.write(self.editor.get("1.0", tk.END))
        messagebox.showinfo("Saved", "File saved successfully")

    def on_edit(self, event=None):
        if hasattr(self, "_debounce_timer"):
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(150, self._delayed_update)

    def _delayed_update(self):
        self._apply_editor_highlight()
        self.update_preview()

    def _apply_editor_highlight(self):
        self.editor.tag_remove("header", "1.0", tk.END)
        self.editor.tag_remove("bold", "1.0", tk.END)
        self.editor.tag_remove("italic", "1.0", tk.END)
        self.editor.tag_remove("list", "1.0", tk.END)
        self.editor.tag_remove("code", "1.0", tk.END)
        content = self.editor.get("1.0", tk.END)
        for line_no, line in enumerate(content.splitlines(), start=1):
            if line.startswith("#"):
                self.editor.tag_add("header", f"{line_no}.0", f"{line_no}.end")
            elif line.startswith(("-", "*", "+")):
                self.editor.tag_add("list", f"{line_no}.0", f"{line_no}.end")
            elif line.startswith("```") or line.startswith("    "):
                self.editor.tag_add("code", f"{line_no}.0", f"{line_no}.end")
            else:
                for match in re.finditer(r"\*\*(.*?)\*\*", line):
                    s, e = match.span()
                    self.editor.tag_add("bold", f"{line_no}.{s}", f"{line_no}.{e}")
                for match in re.finditer(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", line):
                    s, e = match.span()
                    self.editor.tag_add("italic", f"{line_no}.{s}", f"{line_no}.{e}")

    def update_preview(self):
        self.preview.config(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        content = self.editor.get("1.0", tk.END)
        code_block = False
        for idx, line in enumerate(content.splitlines()):
            stripped = line.rstrip("\n")
            tag = None
            display_text = stripped

            if stripped.startswith("```"):
                code_block = not code_block
                continue

            if stripped.strip() == "---":
                self.preview.insert(f"{idx + 1}.0", "─" * 80 + "\n", "hr")
                continue

            if code_block or stripped.startswith("    "):
                tag = "code"
            elif re.match(r"(#{1,6})\s", stripped):
                hashes = re.match(r"(#{1,6})\s", stripped).group(1)
                tag = f"h{len(hashes)}"
                display_text = re.sub(r"^#{1,6}\s*", "", display_text)
            elif re.match(r"[-*+] ", stripped):
                tag = "list"
                display_text = re.sub(r"^[-*+]\s+", "", display_text)
            elif stripped.startswith(">"):
                tag = "blockquote"
                display_text = re.sub(r"^>\s*", "", display_text)
            elif re.match(r"\|.*\|", stripped):
                tag = "table"

            display_text_plain = re.sub(r"\*\*(.*?)\*\*", r"\1", display_text)
            display_text_plain = re.sub(
                r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", r"\1", display_text_plain
            )

            self.preview.insert(f"{idx + 1}.0", display_text_plain + "\n", tag)

            if not (tag and tag.startswith("h")):
                for match in re.finditer(r"\*\*(.*?)\*\*", display_text):
                    s, e = match.span()
                    self.preview.tag_add("bold", f"{idx + 1}.{s}", f"{idx + 1}.{e}")
                for match in re.finditer(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", display_text):
                    s, e = match.span()
                    self.preview.tag_add("italic", f"{idx + 1}.{s}", f"{idx + 1}.{e}")
            for match in re.finditer(r"\[(.*?)\]\((.*?)\)", display_text):
                link_text = match.group(1)
                link_url = match.group(2)
                s, e = match.span()
                self.preview.delete(f"{idx + 1}.{s}", f"{idx + 1}.{e}")
                self.preview.insert(f"{idx + 1}.{s}", link_text, ("link",))
                self.preview.tag_add(
                    link_url, f"{idx + 1}.{s}", f"{idx + 1}.{s + len(link_text)}"
                )

                def make_callback(url):
                    return lambda e: __import__("webbrowser").open(url)

                self.preview.tag_bind(link_url, "<Button-1>", make_callback(link_url))
        self.preview.config(state=tk.NORMAL)

    def export_pdf(self):
        if not self.current_file:
            messagebox.showwarning("No file", "Please save the file first")
            return
        pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf")
        if not pdf_path:
            return
        try:
            content = self.editor.get("1.0", tk.END)

            # 将 Markdown 转 HTML
            html_content = markdown.markdown(
                content,
                extensions=["fenced_code", "tables", "codehilite", "toc", "sane_lists"],
            )

            # Dark 风格 CSS，保留预览区样式，并支持超链接
            css = """
            @page { margin: 0; }
            body {
                margin: 0;
                padding: 15px;
                background-color: #191a1c;
                color: #dcdcdc;
                font-family: Consolas, monospace;
                line-height: 1.4;
            }
            h1 { color: #1f4fd8; font-size: 2em; margin: 0.5em 0; }
            h2 { color: #1f4fd8; font-size: 1.8em; margin: 0.5em 0; }
            h3 { color: #1f4fd8; font-size: 1.6em; margin: 0.5em 0; }
            h4 { color: #1f4fd8; font-size: 1.4em; margin: 0.5em 0; }
            h5 { color: #1f4fd8; font-size: 1.2em; margin: 0.5em 0; }
            h6 { color: #1f4fd8; font-size: 1em; margin: 0.5em 0; }
            p { margin: 0.5em 0; }
            a { color: #8be9fd; text-decoration: underline; }
            a:hover { text-decoration: none; }
            strong { font-weight: bold; }
            em { font-style: italic; }
            blockquote {
                color: #6272a4;
                border-left: 3px solid #6272a4;
                padding-left: 10px;
                margin: 0.5em 0;
            }
            hr { border: none; border-top: 1px solid #dcdcdc; margin: 1em 0; }
            pre, code {
                background-color: #2d2d2d;
                color: #0a7acc;
                padding: 5px;
                border-radius: 3px;
                font-family: Consolas, monospace;
            }
            code { font-size: 0.95em; }
            pre { overflow-x: auto; }
            ul, ol { margin: 0.5em 0 0.5em 1.5em; }
            li { margin: 0.2em 0; }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 0.5em 0;
            }
            th, td {
                border: 1px solid #50fa7b;
                padding: 5px;
            }
            th { background-color: #191a1c; color: #50fa7b; }
            td { background-color: #26282b; color: #dcdcdc; }
            """

            full_html = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>{css}</style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            HTML(string=full_html).write_pdf(pdf_path)
            messagebox.showinfo("Success", f"PDF exported to:\n{pdf_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF:\n{e}")

    def _bind_preview_links(self):
        def open_link(event):
            index = self.preview.index(f"@{event.x},{event.y}")
            tags = self.preview.tag_names(index)
            if "link" in tags:
                line = int(index.split(".")[0])
                for match in re.finditer(
                    r"\[(.*?)\]\((.*?)\)", self.preview.get(f"{line}.0", f"{line}.end")
                ):
                    s, e = match.span()
                    if f"{line}.{s}" <= index <= f"{line}.{e}":
                        url = match.group(2)
                        import webbrowser

                        webbrowser.open(url)
                        break

        self.preview.tag_bind("link", "<Button-1>", open_link)
        self.preview.config(cursor="arrow")  # 默认为箭头，hover link 时可以改成 hand
        self.preview.tag_configure("link", foreground="#8be9fd", underline=True)


if __name__ == "__main__":
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    app = DarkMarkdownEditor(initial)
    app.mainloop()
