import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class CsvFilterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV 字段匹配过滤工具")
        self.geometry("620x360")

        self.csv_path = None
        self.headers = []
        self.rows = []
        self.filtered_rows = []

        self.create_widgets()

    def create_widgets(self):
        # --- 文件选择 ---
        file_frame = ttk.Frame(self)
        file_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            file_frame,
            text="选择 CSV 文件",
            command=self.load_csv
        ).pack(side="left")

        self.file_label = ttk.Label(file_frame, text="未选择文件")
        self.file_label.pack(side="left", padx=10)

        # --- 字段选择 ---
        field_frame = ttk.LabelFrame(self, text="字段匹配规则")
        field_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(field_frame, text="匹配字段（单值）").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.field_a = ttk.Combobox(field_frame, state="disabled")
        self.field_a.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(field_frame, text="目标字段（集合列）").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.field_b = ttk.Combobox(field_frame, state="disabled")
        self.field_b.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        field_frame.columnconfigure(1, weight=1)

        # --- 操作按钮 ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", padx=10, pady=15)

        self.filter_btn = ttk.Button(
            action_frame,
            text="执行过滤",
            state="disabled",
            command=self.filter_rows
        )
        self.filter_btn.pack(side="left")

        self.save_btn = ttk.Button(
            action_frame,
            text="另存为 CSV",
            state="disabled",
            command=self.save_csv
        )
        self.save_btn.pack(side="left", padx=10)

    def load_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV Files", "*.csv")]
        )
        if not path:
            return

        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                self.headers = reader.fieldnames
                self.rows = list(reader)
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
            return

        self.csv_path = path
        self.file_label.config(text=path.split("/")[-1])

        self.field_a.config(values=self.headers, state="readonly")
        self.field_b.config(values=self.headers, state="readonly")
        self.filter_btn.config(state="normal")

    def filter_rows(self):
        field_a = self.field_a.get()
        field_b = self.field_b.get()

        if not field_a or not field_b:
            messagebox.showwarning("提示", "请先选择两个字段")
            return

        # 构建目标字段的值集合
        value_set = {
            (row.get(field_b) or "").strip()
            for row in self.rows
            if row.get(field_b)
        }

        self.filtered_rows = [
            row for row in self.rows
            if (row.get(field_a) or "").strip() in value_set
        ]

        self.save_btn.config(state="normal")

        messagebox.showinfo(
            "完成",
            f"原始行数：{len(self.rows)}\n保留行数：{len(self.filtered_rows)}"
        )

    def save_csv(self):
        if not self.filtered_rows:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.filtered_rows)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return

        messagebox.showinfo("成功", "CSV 文件已保存")


if __name__ == "__main__":
    app = CsvFilterApp()
    app.mainloop()

