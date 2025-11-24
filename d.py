#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk

root = tk.Tk()

# 使用 ttk 控件
btn = ttk.Button(root, text="点击我")
btn.pack(padx=10, pady=10)

root.mainloop()
