#!/usr/bin/env python3
"""Excel/CSV -> JSON Converter (Tkinter)

Python3 + Tkinter tool to convert Excel (first sheet only) or CSV into JSON.

支持：
- CSV 文件（不依赖第三方库）
- XLS/XLSX 等 Excel 文件（需要 openpyxl）

规则：
- 只读取第一个工作表（对于 Excel），或整个 CSV 文件。
- 第一行为字段名，从第二行起为数据。

第三方库策略：
- 优先使用标准库，CSV 通过内置 csv 模块解析，不需要任何第三方库。
- 只有当用户选择 .xls/.xlsx 等 Excel 文件时，才需要 openpyxl。
  若未安装 openpyxl，则给出友好提示：请安装后再使用 Excel 解析功能。
- 若仅使用 CSV，则不会提示安装 openpyxl。

运行: python3 convert-excel.py
"""

import csv
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# openpyxl 相关：延迟/可选导入
try:
    from openpyxl import load_workbook  # type: ignore
    _HAS_OPENPYXL = True
except Exception:
    # 不强制安装；只有在解析 Excel 时才会检查
    _HAS_OPENPYXL = False


class ExcelToJsonApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Excel/CSV 转 JSON 工具")
        self.geometry("780x420")
        self.resizable(False, False)

        self.file_path = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()

    def _build_ui(self):
        pad = 10
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill=tk.BOTH, expand=True)

        # 选择文件
        lbl_file = ttk.Label(frm, text="输入文件：")
        lbl_file.grid(row=0, column=0, sticky="w")

        entry_file = ttk.Entry(frm, textvariable=self.file_path, width=60)
        entry_file.grid(row=0, column=1, sticky="we", padx=(0, 5))

        btn_browse = ttk.Button(frm, text="选择文件", command=self.browse_file)
        btn_browse.grid(row=0, column=2, sticky="e")

        # 说明
        lbl_info = ttk.Label(
            frm,
            text=(
                "说明：支持 CSV、XLS、XLSX。只读取第一个 sheet/整表，"
                "第一行为字段名，从第二行起为数据。"
            ),
            foreground="#444",
        )
        lbl_info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 4))

        # 预览与转换按钮
        btn_preview = ttk.Button(frm, text="预览 JSON", command=self.preview_json)
        btn_preview.grid(row=2, column=0, sticky="w", pady=(4, 4))

        btn_convert = ttk.Button(frm, text="转换为 JSON 并保存", command=self.convert_and_save)
        btn_convert.grid(row=2, column=2, sticky="e", pady=(4, 4))

        # 预览区域
        lbl_preview = ttk.Label(frm, text="JSON 预览（最多显示前 20 条）：")
        lbl_preview.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.text_preview = tk.Text(frm, height=12, width=90)
        self.text_preview.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(4, 0))

        # 滚动条
        scroll = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.text_preview.yview)
        scroll.grid(row=4, column=3, sticky="nsw")
        self.text_preview.config(yscrollcommand=scroll.set)

        # 状态栏
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.pack(side=tk.BOTTOM, fill=tk.X)

        # grid 行列权重
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

    # ----------------- 文件选择 -----------------

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="选择 CSV 或 Excel 文件",
            filetypes=[
                ("表格文件", "*.csv *.xls *.xlsx *.xlsm *.xltx *.xltm"),
                ("CSV", "*.csv"),
                ("Excel", "*.xls *.xlsx *.xlsm *.xltx *.xltm"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.file_path.set(path)
            self.status_var.set(f"已选择文件: {os.path.basename(path)}")

    # ----------------- 数据读取 -----------------

    def _read_csv(self, path):
        """使用标准库 csv 读取数据，第一行作为字段名。"""
        data = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader, None)
            except StopIteration:
                headers = None
            if not headers:
                raise ValueError("CSV 文件为空或没有表头")
            headers = [str(h).strip() if h is not None else "" for h in headers]
            if not any(headers):
                raise ValueError("第一行没有有效的字段名")

            for row in reader:
                if not any(cell.strip() for cell in row if isinstance(cell, str)) and all(
                    cell in (None, "") for cell in row
                ):
                    # 整行为空
                    continue
                item = {}
                for key, value in zip(headers, row):
                    if not key:
                        continue
                    item[key] = value
                if item:
                    data.append(item)
        return data

    def _read_excel_first_sheet(self, path):
        """Read first sheet, treat first row as headers. Return list of dicts.
        需要 openpyxl。
        """
        if not _HAS_OPENPYXL:
            raise RuntimeError("解析 Excel 文件需要 openpyxl，请先执行: pip install openpyxl/sudo apt install python3-openpyxl")

        wb = load_workbook(path, read_only=True, data_only=True)
        sheet = wb.worksheets[0]  # 第一个 sheet

        rows = list(sheet.rows)
        if not rows:
            raise ValueError("Excel 文件为空或第一个 sheet 没有数据")

        # 第一行字段名
        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[0]]

        if not any(headers):
            raise ValueError("第一行没有有效的字段名")

        data = []
        for row in rows[1:]:  # 从第二行起为数据
            values = [cell.value for cell in row]
            # 如果整行为空，则跳过
            if all(v is None for v in values):
                continue
            item = {}
            for key, value in zip(headers, values):
                if not key:
                    # 忽略空字段名的列
                    continue
                item[key] = value
            if item:
                data.append(item)
        return data

    def _load_data(self):
        path = self.file_path.get().strip()
        if not path:
            raise ValueError("请先选择文件")
        if not os.path.exists(path):
            raise ValueError("文件不存在")

        ext = os.path.splitext(path)[1].lower()

        self.status_var.set("正在读取数据...")
        self.update_idletasks()

        if ext == ".csv":
            data = self._read_csv(path)
        elif ext in {".xls", ".xlsx", ".xlsm", ".xltx", ".xltm"}:
            data = self._read_excel_first_sheet(path)
        else:
            raise ValueError("不支持的文件类型，请选择 CSV 或 Excel 文件")

        self.status_var.set(f"读取完成，共 {len(data)} 条记录")
        return data

    # ----------------- 按钮动作 -----------------

    def preview_json(self):
        try:
            data = self._load_data()
            # 仅显示前 20 条
            preview_data = data[:20]
            txt = json.dumps(preview_data, ensure_ascii=False, indent=2)
            self.text_preview.delete("1.0", tk.END)
            self.text_preview.insert(tk.END, txt)
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set("错误")

    def convert_and_save(self):
        try:
            data = self._load_data()
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return

        if not data:
            messagebox.showwarning("提示", "没有可导出的数据")
            return

        # 默认文件名
        default_name = os.path.splitext(os.path.basename(self.file_path.get()))[0] + ".json"

        save_path = filedialog.asksaveasfilename(
            title="保存 JSON 文件",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
        )
        if not save_path:
            return

        try:
            self.status_var.set("正在写入 JSON 文件...")
            self.update_idletasks()
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status_var.set("转换完成")
            messagebox.showinfo("完成", f"已保存到: {save_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
            self.status_var.set("错误")


if __name__ == "__main__":
    app = ExcelToJsonApp()
    app.mainloop()

