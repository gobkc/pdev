import json
import tkinter as tk
from tkinter import ttk, messagebox

class JSONAggregatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON 字段累加工具")
        self.root.geometry("600x400")

        # 文本框输入 JSON
        tk.Label(root, text="粘贴 JSON 数据:").pack(anchor='w', padx=10, pady=5)
        self.text = tk.Text(root, height=10, width=70, undo=True)  # undo=True 支持 Ctrl+Z
        self.text.pack(padx=10, pady=5)

        # 绑定常用快捷键
        self.text.bind("<Control-a>", self.select_all)
        self.text.bind("<Control-A>", self.select_all)
        # Ctrl+C、Ctrl+X、Ctrl+V 默认已经支持

        # 字段选择下拉框
        tk.Label(root, text="选择字段进行累加:").pack(anchor='w', padx=10, pady=5)
        self.field_var = tk.StringVar()
        self.field_dropdown = ttk.Combobox(root, textvariable=self.field_var, state="readonly")
        self.field_dropdown.pack(padx=10, pady=5)

        # 按钮
        button_frame = tk.Frame(root)
        button_frame.pack(pady=5)

        self.load_fields_btn = tk.Button(button_frame, text="加载字段", command=self.load_fields)
        self.load_fields_btn.grid(row=0, column=0, padx=5)

        self.calculate_btn = tk.Button(button_frame, text="统计", command=self.calculate_sum)
        self.calculate_btn.grid(row=0, column=1, padx=5)

        self.clear_btn = tk.Button(button_frame, text="清空", command=self.clear_content)
        self.clear_btn.grid(row=0, column=2, padx=5)

        # 显示结果
        self.result_label = tk.Label(root, text="结果: 0", font=("Arial", 14))
        self.result_label.pack(padx=10, pady=20)

        self.json_data = []

    def select_all(self, event=None):
        self.text.tag_add("sel", "1.0", "end")
        return 'break'

    def load_fields(self):
        text_content = self.text.get("1.0", tk.END).strip()
        if not text_content:
            messagebox.showerror("错误", "请先粘贴 JSON 数据")
            return

        try:
            data = json.loads(text_content)
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "JSON 数据格式错误！必须是列表，且每个元素为字典。")
            return

        self.json_data = data
        fields = list(data[0].keys())
        self.field_dropdown['values'] = fields
        if fields:
            self.field_dropdown.current(0)

    def calculate_sum(self):
        if not self.json_data:
            messagebox.showerror("错误", "请先加载字段")
            return

        field = self.field_var.get()
        if not field:
            messagebox.showerror("错误", "请选择一个字段")
            return

        total = 0
        for item in self.json_data:
            value = item.get(field, 0)
            if isinstance(value, (int, float)):
                total += value

        self.result_label.config(text=f"结果: {total}")

    def clear_content(self):
        self.text.delete("1.0", tk.END)
        self.result_label.config(text="结果: 0")
        self.field_dropdown['values'] = []
        self.field_var.set("")
        self.json_data = []

if __name__ == "__main__":
    root = tk.Tk()
    app = JSONAggregatorApp(root)
    root.mainloop()

