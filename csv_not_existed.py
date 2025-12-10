import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv

class CSVParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Parser Tool")
        self.root.geometry("800x600")

        self.file_path = None
        self.headers = []
        self.rows = []

        # 文件选择
        self.btn_select_file = tk.Button(root, text="Select CSV File", command=self.select_file)
        self.btn_select_file.pack(pady=10)

        self.lbl_file = tk.Label(root, text="No file selected")
        self.lbl_file.pack(pady=5)

        # 字段 A 和 B 下拉框
        tk.Label(root, text="Field A:").pack(pady=5)
        self.field_a_var = tk.StringVar()
        self.combo_field_a = ttk.Combobox(root, textvariable=self.field_a_var, state="readonly")
        self.combo_field_a.pack(pady=2)

        tk.Label(root, text="Field B:").pack(pady=5)
        self.field_b_var = tk.StringVar()
        self.combo_field_b = ttk.Combobox(root, textvariable=self.field_b_var, state="readonly")
        self.combo_field_b.pack(pady=2)

        # Parse 按钮
        self.btn_parse = tk.Button(root, text="Parse", command=self.parse_csv)
        self.btn_parse.pack(pady=10)

        # 保存按钮
        self.btn_save = tk.Button(root, text="Save Result", command=self.save_result, state=tk.DISABLED)
        self.btn_save.pack(pady=5)

        self.result_rows = []

    def select_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if self.file_path:
            self.lbl_file.config(text=self.file_path)
            with open(self.file_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.headers = next(reader)
                # 读取所有行，去掉每个单元格的前后空格和换行
                self.rows = []
                for row in reader:
                    cleaned_row = [cell.strip() for cell in row]
                    self.rows.append(dict(zip(self.headers, cleaned_row)))
            # 更新下拉框
            self.combo_field_a['values'] = self.headers
            self.combo_field_b['values'] = self.headers
            messagebox.showinfo("Info", f"CSV loaded. Fields: {', '.join(self.headers)}")

    def parse_csv(self):
        field_a = self.field_a_var.get()
        field_b = self.field_b_var.get()

        if not self.file_path:
            messagebox.showerror("Error", "Please select a CSV file first.")
            return
        if field_a not in self.headers or field_b not in self.headers:
            messagebox.showerror("Error", "Field A or Field B not selected correctly.")
            return

        set_a = set(row[field_a] for row in self.rows)
        # 筛选 B 字段中存在但 A 字段中不存在的整行
        self.result_rows = [row for row in self.rows if row[field_b] not in set_a]

        messagebox.showinfo("Result", f"Found {len(self.result_rows)} records in Field B not in Field A")
        self.btn_save.config(state=tk.NORMAL)

    def save_result(self):
        if not self.result_rows:
            messagebox.showerror("Error", "No result to save.")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if save_path:
            with open(save_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.result_rows)
            messagebox.showinfo("Saved", f"Result saved to {save_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CSVParserApp(root)
    root.mainloop()

