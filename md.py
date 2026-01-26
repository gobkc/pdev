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
        self.configure(bg="#2b2b2b")
        self.current_file = None
        self.current_folder = None
        self._build_ui()
        self._bind_shortcuts()
        if initial_file and os.path.isfile(initial_file):
            self.load_file_async(initial_file)

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="#dcdcdc",
            fieldbackground="#2b2b2b",
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", "#44475a")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#44475a",
            troughcolor="#2b2b2b",
            arrowcolor="#dcdcdc",
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", "#2b2b2b")],
            troughcolor=[("active", "#2b2b2b")],
        )
        toolbar = tk.Frame(self, bg="#2b2b2b")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        for text, cmd, shortcut, icon in [
            ("Open Folder", self.open_folder, "Ctrl+Shift+O", "📂"),
            ("Open", self.open_file, "Ctrl+O", "📄"),
            ("Save", self.save_file, "Ctrl+S", "💾"),
            ("Export PDF", self.export_pdf, "Ctrl+P", "📑"),
        ]:
            btn = tk.Button(
                toolbar,
                text=f"{icon} {text} ({shortcut})",
                bg="#44475a",
                fg="#dcdcdc",
                relief=tk.FLAT,
                activebackground="#555555",
                activeforeground="#ffffff",
                anchor="w",
                font=("Consolas", 11),
                padx=8,
                pady=4,
                command=cmd,
            )
            btn.pack(side=tk.LEFT, padx=4, pady=2)
            self._add_button_hover(btn)

        main = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4, bg="#2b2b2b")
        main.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(main, width=220, bg="#2b2b2b")
        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.open_from_tree)
        main.add(left)

        center = tk.Frame(main, bg="#2b2b2b")
        self.editor = tk.Text(
            center,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg="#2b2b2b",
            fg="#dcdcdc",
            insertbackground="white",
            selectbackground="#555555",
            undo=True,
            borderwidth=1,
            relief=tk.SOLID,
            highlightbackground="#000000",
            highlightcolor="#000000",
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
        main.add(center)

        right = tk.Frame(main, bg="#2b2b2b")
        self.preview = tk.Text(
            right,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg="#2b2b2b",
            fg="#dcdcdc",
            insertbackground="white",
            selectbackground="#555555",
            borderwidth=1,
            relief=tk.SOLID,
            highlightbackground="#000000",
            highlightcolor="#000000",
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
        main.add(right)

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
        self.preview.tag_configure("th", foreground="#50fa7b", background="#44475a")
        self.preview.tag_configure("td", foreground="#f8f8f2", background="#2d2d2d")
        self.preview.tag_configure("hr", foreground="#dcdcdc", underline=False)

    def _add_button_hover(self, btn):
        btn.bind("<Enter>", lambda e: btn.config(bg="#555555"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#44475a"))

    def _bind_shortcuts(self):
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

    def open_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.current_folder = path
            self._list_markdown_files(path)

    def _list_markdown_files(self, folder_path):
        self.tree.delete(*self.tree.get_children())
        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith(".md"):
                full_path = os.path.join(folder_path, filename)
                self.tree.insert("", "end", text=filename, values=[full_path])

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
                s, e = match.span()
                self.preview.tag_add("link", f"{idx + 1}.{s}", f"{idx + 1}.{e}")

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
            html = markdown.markdown(content, extensions=["fenced_code", "tables"])
            html = f"<body style='padding:15px;background-color:#2b2b2b;color:#dcdcdc;font-family:Consolas;margin:0'>{html}</body>"
            HTML(string=html).write_pdf(pdf_path)
            messagebox.showinfo("Success", f"PDF exported to:\n{pdf_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF:\n{e}")


if __name__ == "__main__":
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    app = DarkMarkdownEditor(initial)
    app.mainloop()
