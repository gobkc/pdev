#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import csv
import os

# --- SQL 处理函数 ---
def sql_quote(val):
    """将 Python 值转为 SQL 字面量"""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).strip()
    return "'" + s.replace("'", "''") + "'"

def generate_sql(csv_file):
    FIELD_DEPT_ID = "Department ID"
    FIELD_DEPT_NAME = "Department Name"
    FIELD_STATE = "Wilayat Code"

    sql_lines = []
    skipped_rows = 0

    with open(csv_file, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # 去除字段名前后空格
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        # 检查必要字段是否存在
        missing = [fld for fld in (FIELD_DEPT_ID, FIELD_DEPT_NAME, FIELD_STATE) if fld not in reader.fieldnames]
        if missing:
            raise ValueError("CSV 中缺少以下字段: {}".format(", ".join(missing)))

        for row in reader:
            # 去掉每个字段值的前后空格
            row = {k.strip(): (v.strip() if v is not None else "") for k, v in row.items()}

            dept_id = row.get(FIELD_DEPT_ID, "")
            dept_name = row.get(FIELD_DEPT_NAME, "")
            state_val = row.get(FIELD_STATE, "")

            if not dept_id:
                skipped_rows += 1
                continue

            # 映射到 org_chart 字段
            group_name = dept_name
            employee_position_number = dept_id
            city = state_val
            country = "Oman"
            region = ""
            province = city[:2] if len(city) >= 4 else ""

            set_clauses = [
                f"group_name={sql_quote(group_name)}",
                f"country={sql_quote(country)}",
                f"province={sql_quote(province)}",
                f"city={sql_quote(city)}",
                f"region={sql_quote(region)}",
            ]

            sql = (
                "UPDATE org_chart SET " +
                ", ".join(set_clauses) +
                f" WHERE employee_position_number={sql_quote(employee_position_number)};"
            )
            sql_lines.append(sql)

    return sql_lines, skipped_rows

# --- GUI 事件处理 ---
def choose_file():
    file_path = filedialog.askopenfilename(
        title="选择 CSV 文件",
        filetypes=[("CSV Files", "*.csv")]
    )
    if file_path:
        entry_file_path.delete(0, tk.END)
        entry_file_path.insert(0, file_path)

def generate_and_save():
    csv_file = entry_file_path.get().strip()
    if not csv_file or not os.path.isfile(csv_file):
        messagebox.showerror("错误", "请选择有效的 CSV 文件")
        return

    try:
        sql_lines, skipped = generate_sql(csv_file)
        sql_file_name = csv_file + ".sql"
        with open(sql_file_name, "w", encoding="utf-8") as f:
            for line in sql_lines:
                f.write(line + "\n")
        text_log.delete("1.0", tk.END)
        text_log.insert(tk.END, f"成功生成 SQL 文件: {sql_file_name}\n")
        text_log.insert(tk.END, f"生成行数: {len(sql_lines)}, 跳过空 Department ID 行: {skipped}\n")
    except Exception as e:
        messagebox.showerror("错误", str(e))

# --- GUI 主窗口 ---
root = tk.Tk()
root.title("CSV -> SQL 生成器")
root.geometry("600x400")

# 文件选择
frame_file = tk.Frame(root)
frame_file.pack(padx=10, pady=10, fill=tk.X)

label_file = tk.Label(frame_file, text="CSV 文件:")
label_file.pack(side=tk.LEFT)

entry_file_path = tk.Entry(frame_file)
entry_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

btn_browse = tk.Button(frame_file, text="浏览", command=choose_file)
btn_browse.pack(side=tk.LEFT)

# 生成 SQL 按钮
btn_generate = tk.Button(root, text="生成 SQL", command=generate_and_save)
btn_generate.pack(pady=5)

# 日志显示
text_log = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=15)
text_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# 启动 GUI
root.mainloop()
