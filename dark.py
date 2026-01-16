import tkinter as tk
import flat_dark_theme as theme

root = tk.Tk()
root.title("Flat Dark Tkinter Demo")
root.geometry("400x250")
root.configure(bg=theme.THEME["bg"])

# Frame
frame = tk.Frame(root)
frame.pack(padx=20, pady=20, fill="both", expand=True)

# Label
lbl = tk.Label(frame, text="Username:")
lbl.pack(anchor="w", pady=5)

# Entry
entry = tk.Entry(frame)
entry.pack(fill="x", pady=5)

# Button
btn = tk.Button(frame, text="Login")
btn.pack(pady=10)

# Checkbutton
chk = tk.Checkbutton(frame, text="Remember me")
chk.pack(pady=5)

# Radiobutton
rb1 = tk.Radiobutton(frame, text="Option 1", value=1)
rb2 = tk.Radiobutton(frame, text="Option 2", value=2)
rb1.pack(pady=2)
rb2.pack(pady=2)

# 应用主题到所有控件
theme.apply_theme_recursive(root)

root.mainloop()

