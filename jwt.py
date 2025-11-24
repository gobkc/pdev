#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import base64
import json

# --- 解析 JWT Payload ---
def parse_jwt():
    jwt_str = entry_jwt.get().strip()
    if not jwt_str:
        messagebox.showerror("错误", "请输入 JWT 字符串")
        return

    parts = jwt_str.split(".")
    if len(parts) != 3:
        messagebox.showerror("错误", "JWT 格式不正确，应为 header.payload.signature")
        return

    payload_b64 = parts[1]

    # JWT base64url 解码
    try:
        # base64url 补齐
        missing_padding = len(payload_b64) % 4
        if missing_padding:
            payload_b64 += '=' * (4 - missing_padding)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload_json = json.loads(payload_bytes.decode("utf-8"))

        # 格式化输出
        payload_formatted = json.dumps(payload_json, indent=4, ensure_ascii=False)
        text_output.config(state="normal")
        text_output.delete("1.0", tk.END)
        text_output.insert(tk.END, payload_formatted)
        text_output.config(state="disabled")
    except Exception as e:
        messagebox.showerror("错误", f"解析失败: {str(e)}")

# --- GUI ---
root = tk.Tk()
root.title("JWT Payload 解析器")
root.geometry("700x500")

# 使用 ttk 主题
style = ttk.Style(root)
style.theme_use("clam")

# 输入 JWT
frame_input = ttk.Frame(root, padding=10)
frame_input.pack(fill=tk.X)

label_jwt = ttk.Label(frame_input, text="JWT 字符串:")
label_jwt.pack(side=tk.LEFT)

entry_jwt = ttk.Entry(frame_input)
entry_jwt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

btn_parse = ttk.Button(frame_input, text="解析 Payload", command=parse_jwt)
btn_parse.pack(side=tk.LEFT)

# 输出结果
text_output = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=25, state="disabled")
text_output.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

root.mainloop()
