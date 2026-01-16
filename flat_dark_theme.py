# flat_dark_theme.py
import tkinter as tk

# ----------------------------
# 主题配置
# ----------------------------
THEME = {
    "bg": "#2e2e2e",              # 窗口/Frame 背景
    "fg": "#ffffff",              # 文字颜色
    "button_bg": "#444444",       # Button 默认背景
    "button_hover": "#555555",    # Button 悬停背景
    "entry_bg": "#3a3a3a",        # Entry/Text 背景
    "entry_fg": "#ffffff",        # Entry/Text 文字
    "frame_bg": "#2e2e2e",        # Frame 背景
    "border_color": "#555555",    # Entry/Text 边框
    "font": ("Segoe UI", 10),     # 默认字体
}

# ----------------------------
# 单控件美化函数
# ----------------------------
def flat_button(button: tk.Button):
    button.configure(
        bg=THEME["button_bg"],
        fg=THEME["fg"],
        activebackground=THEME["button_hover"],
        activeforeground=THEME["fg"],
        relief="flat",
        bd=0,
        font=THEME["font"],
        highlightthickness=0,
        cursor="hand2"
    )
    # 悬停效果
    button.bind("<Enter>", lambda e: button.config(bg=THEME["button_hover"]))
    button.bind("<Leave>", lambda e: button.config(bg=THEME["button_bg"]))

def flat_entry(entry: tk.Entry):
    entry.configure(
        bg=THEME["entry_bg"],
        fg=THEME["entry_fg"],
        insertbackground=THEME["fg"],
        relief="flat",
        bd=1,
        highlightthickness=1,
        highlightbackground=THEME["border_color"],
        highlightcolor=THEME["button_hover"],
        font=THEME["font"]
    )

def flat_label(label: tk.Label):
    label.configure(
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=THEME["font"]
    )

def flat_frame(frame: tk.Frame):
    frame.configure(
        bg=THEME["frame_bg"]
    )

def flat_text(text: tk.Text):
    text.configure(
        bg=THEME["entry_bg"],
        fg=THEME["entry_fg"],
        insertbackground=THEME["fg"],
        relief="flat",
        bd=1,
        highlightthickness=1,
        highlightbackground=THEME["border_color"],
        highlightcolor=THEME["button_hover"],
        font=THEME["font"]
    )

def flat_check_radiobutton(widget: tk.Widget):
    """
    支持 Checkbutton 和 Radiobutton
    扁平化 + 背景一致 + 无 indicator（可选）
    """
    widget.configure(
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=THEME["font"],
        selectcolor=THEME["button_hover"],
        indicatoron=0,
        relief="flat",
        bd=0,
        activebackground=THEME["button_hover"]
    )

# ----------------------------
# 递归应用主题
# ----------------------------
def apply_theme(widget: tk.Widget):
    """
    单个控件应用对应主题
    """
    if isinstance(widget, tk.Button):
        flat_button(widget)
    elif isinstance(widget, tk.Entry):
        flat_entry(widget)
    elif isinstance(widget, tk.Label):
        flat_label(widget)
    elif isinstance(widget, tk.Frame):
        flat_frame(widget)
    elif isinstance(widget, tk.Text):
        flat_text(widget)
    elif isinstance(widget, (tk.Checkbutton, tk.Radiobutton)):
        flat_check_radiobutton(widget)

def apply_theme_recursive(widget: tk.Widget):
    """
    对窗口及所有子控件递归应用主题
    """
    apply_theme(widget)
    for child in widget.winfo_children():
        apply_theme_recursive(child)

