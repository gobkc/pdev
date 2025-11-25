#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from collections import Counter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class JsonFieldCounterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSON 字段统计工具")
        self.geometry("800x600")
        self.resizable(True, True)

        self.json_path = tk.StringVar()
        self.field_name = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")
        self.count_result = ""  # 保存结果字符串，方便导出
        self.available_fields_var = tk.StringVar(value="（尚未选择文件）")

        self._build_ui()

    def _build_ui(self):
        pad = 10
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill=tk.BOTH, expand=True)

        # 选择文件
        lbl_file = ttk.Label(frm, text="JSON 文件：")
        lbl_file.grid(row=0, column=0, sticky="w")

        entry_file = ttk.Entry(frm, textvariable=self.json_path, width=50)
        entry_file.grid(row=0, column=1, sticky="we", padx=(0, 5))

        btn_browse = ttk.Button(frm, text="选择文件", command=self.browse_file)
        btn_browse.grid(row=0, column=2, sticky="e")

        # 可用字段提示
        lbl_available_title = ttk.Label(frm, text="当前文件字段名（来自第一个元素）：")
        lbl_available_title.grid(row=1, column=0, sticky="nw", pady=(8, 0))

        lbl_available = ttk.Label(
            frm,
            textvariable=self.available_fields_var,
            foreground="#0066aa",
            wraplength=600,
            justify="left",
        )
        lbl_available.grid(row=1, column=1, columnspan=2, sticky="w", pady=(8, 0))

        # 字段名输入
        lbl_field = ttk.Label(frm, text="统计字段名：")
        lbl_field.grid(row=2, column=0, sticky="w", pady=(8, 4))

        entry_field = ttk.Entry(frm, textvariable=self.field_name, width=20)
        entry_field.grid(row=2, column=1, sticky="w", pady=(8, 4))

        # 说明
        lbl_info = ttk.Label(
            frm,
            text=(
                "说明：JSON 须为数组结构，如 [ {\"name\":\"ali\",\"age\":18}, ... ]。\n"
                "从第一个元素中读取字段名用于提示。统计时，字符串会自动去除前后空格，"
                "缺失或空值会归入虚拟分组 other。统计结果按字段名 a-z 排序，other 始终放最后。"
            ),
            foreground="#444",
            wraplength=700,
            justify="left",
        )
        lbl_info.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 8))

        # 按钮
        btn_count = ttk.Button(frm, text="统计", command=self.do_count)
        btn_count.grid(row=4, column=0, sticky="w", pady=(4, 4))

        btn_save = ttk.Button(frm, text="保存结果到文件", command=self.save_result)
        btn_save.grid(row=4, column=2, sticky="e", pady=(4, 4))

        # 结果区域
        lbl_result = ttk.Label(frm, text="统计结果：")
        lbl_result.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.text_result = tk.Text(frm, height=15, width=90)
        self.text_result.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(4, 0))

        scroll = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.text_result.yview)
        scroll.grid(row=6, column=3, sticky="nsw")
        self.text_result.config(yscrollcommand=scroll.set)

        # 状态栏
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.pack(side=tk.BOTTOM, fill=tk.X)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(6, weight=1)

    # ------------- 事件方法 -------------

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="选择 JSON 文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.json_path.set(path)
            self.status_var.set(f"已选择文件: {os.path.basename(path)}")
            # 选择文件后立即尝试加载字段名
            self._update_available_fields(path)

    def _load_json_list(self, path):
        """加载 JSON 文件，确保是 list 结构。"""
        if not os.path.exists(path):
            raise ValueError("文件不存在")

        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON 解析失败: {e}")

        if not isinstance(data, list):
            raise ValueError("JSON 根结构必须是数组 (list)")

        return data

    def _update_available_fields(self, path):
        """从 JSON 的第一个元素中读取字段名，并更新到 label。"""
        try:
            data_list = self._load_json_list(path)
        except Exception as e:
            self.available_fields_var.set(f"解析失败：{e}")
            return

        if not data_list:
            self.available_fields_var.set("文件中没有任何元素")
            return

        first = data_list[0]
        if not isinstance(first, dict):
            self.available_fields_var.set("第一个元素不是对象（不是 {} 结构），无法读取字段名")
            return

        keys = list(first.keys())
        if not keys:
            self.available_fields_var.set("第一个元素没有字段")
            return

        self.available_fields_var.set(", ".join(str(k) for k in keys))

    def do_count(self):
        path = self.json_path.get().strip()
        field = self.field_name.get().strip()

        if not path:
            messagebox.showwarning("提示", "请先选择 JSON 文件")
            return
        if not field:
            messagebox.showwarning("提示", "请输入要统计的字段名")
            return

        try:
            self.status_var.set("正在加载 JSON 数据...")
            self.update_idletasks()

            data_list = self._load_json_list(path)

            self.status_var.set("正在统计...")
            self.update_idletasks()

            counter = Counter()
            missing_or_empty_count = 0

            for item in data_list:
                if not isinstance(item, dict):
                    missing_or_empty_count += 1
                    continue

                if field not in item:
                    missing_or_empty_count += 1
                    continue

                value = item[field]

                # 去除前后空格（仅对字符串）
                if isinstance(value, str):
                    value = value.strip()

                # 空值归入 other
                if value is None or (isinstance(value, str) and value == ""):
                    missing_or_empty_count += 1
                else:
                    counter[value] += 1

            # 添加 other
            if missing_or_empty_count > 0:
                counter["other"] += missing_or_empty_count

            # 生成报告文本
            lines = []
            lines.append(f"文件：{os.path.basename(path)}")
            lines.append(f"统计字段：{field}")
            lines.append(f"总记录数：{len(data_list)}")
            lines.append("")
            lines.append("值\t:\t数量")
            lines.append("-" * 40)

            # 排序：按 key 名 a-z 排序，other 始终放最后
            items = sorted((k, v) for k, v in counter.items() if k != "other")
            if "other" in counter:
                items.append(("other", counter["other"]))

            for value, cnt in items:
                lines.append(f"{value}\t:\t{cnt}")

            result_text = "\n".join(lines)
            self.count_result = result_text

            self.text_result.delete("1.0", tk.END)
            self.text_result.insert(tk.END, result_text)

            self.status_var.set("统计完成")

        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set("错误")

    def save_result(self):
        if not self.count_result.strip():
            messagebox.showinfo("提示", "还没有统计结果可以保存，请先点击“统计”。")
            return

        default_name = "report.txt"
        if self.json_path.get():
            base = os.path.splitext(os.path.basename(self.json_path.get()))[0]
            default_name = base + "_report.txt"

        save_path = filedialog.asksaveasfilename(
            title="保存统计结果",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.count_result)
            messagebox.showinfo("完成", f"统计结果已保存到：{save_path}")
            self.status_var.set("保存完成")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")
            self.status_var.set("错误")


if __name__ == "__main__":
    app = JsonFieldCounterApp()
    app.mainloop()

