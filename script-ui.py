#!/usr/bin/env python3
import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


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
    FIELD_PARENT_DEPT_ID = "Parent Department ID"
    FIELD_DEPT_NAME = "Department Name"
    FIELD_STATE = "Code"
    FIELD_LOCATION = "Location Code"
    sql_lines = []
    skipped_rows = 0

    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        required = [FIELD_DEPT_ID, FIELD_PARENT_DEPT_ID, FIELD_DEPT_NAME, FIELD_STATE]
        missing = [f for f in required if f not in reader.fieldnames]
        if missing:
            raise ValueError("CSV 中缺少字段: " + ", ".join(missing))

        for row in reader:
            row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}

            dept_id = row[FIELD_DEPT_ID]
            parent_dept_id = row[FIELD_PARENT_DEPT_ID]
            dept_name = row[FIELD_DEPT_NAME]
            state_val = row[FIELD_STATE]
            region = row[FIELD_LOCATION]

            if not dept_id:
                skipped_rows += 1
                continue

            province = state_val[:2] if len(state_val) >= 4 else ""

            # -------- UPDATE --------
            sql_lines.append(
                f"""
UPDATE org_chart SET
    group_name = {sql_quote(dept_name)},
    supervisor_position_number = {sql_quote(parent_dept_id)},
    country = 'Oman',
    province = {sql_quote(province)},
    region = {sql_quote(region)},
    city = {sql_quote(state_val)}
WHERE employee_position_number = {sql_quote(dept_id)};
""".strip()
            )

            # -------- INSERT (不存在时) --------
            sql_lines.append(
                f"""
INSERT INTO org_chart (
    employee_position_number,
    supervisor_position_number,
    group_name,
    description,
    country,
    province,
    region,
    city
)
SELECT
    {sql_quote(dept_id)},
    {sql_quote(parent_dept_id)},
    {sql_quote(dept_name)},
    '(pending)',
    'Oman',
    {sql_quote(province)},
    {sql_quote(region)},
    {sql_quote(state_val)}
WHERE NOT EXISTS (
    SELECT 1 FROM org_chart
    WHERE employee_position_number = {sql_quote(dept_id)}
);
""".strip()
            )

    # -------- 后处理 SQL --------

    # Step 1：写 org_id
    sql_lines.append(
        """
-- Step 1: propagate org_id
UPDATE org_chart
SET org_id = (
    SELECT org_id
    FROM org_chart
    WHERE employee_position_number = '623D9EF0-9A50-4558-B83D-8CC27A1A0EDB'
    LIMIT 1
), company_id = (
    SELECT company_id
    FROM org_chart
    WHERE employee_position_number = '623D9EF0-9A50-4558-B83D-8CC27A1A0EDB'
    LIMIT 1
)
WHERE description = '(pending)';
""".strip()
    )

    # Step 2：处理其他level 1,以：623D9EF0-9A50-4558-B83D-8CC27A1A0EDB为准
    sql_lines.append(
        """
-- Step 2: propagate org_id
UPDATE org_chart
SET parent_id = (
    SELECT parent_id
    FROM org_chart
    WHERE employee_position_number = '623D9EF0-9A50-4558-B83D-8CC27A1A0EDB'
    LIMIT 1
)
WHERE supervisor_position_number = '00000000-0000-0000-0000-000000000000' AND employee_position_number!='623D9EF0-9A50-4558-B83D-8CC27A1A0EDB';
""".strip()
    )

    # Step 3：补 parent_id
    sql_lines.append(
        """
-- Step 2: fill parent_id
UPDATE org_chart AS child
SET parent_id = parent.id
FROM org_chart AS parent
WHERE parent.supervisor_position_number!=''
  AND child.org_id = parent.org_id
  AND child.supervisor_position_number = parent.employee_position_number;
""".strip()
    )

    # Step 4：remove pending
    sql_lines.append(
        """
-- Step 3: remove pending
UPDATE org_chart
SET description = '', sort = id
WHERE description = '(pending)';
""".strip()
    )

    return sql_lines, skipped_rows


# --- GUI 事件处理 ---
def choose_file():
    file_path = filedialog.askopenfilename(
        title="选择 CSV 文件", filetypes=[("CSV Files", "*.csv")]
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
        text_log.insert(
            tk.END, f"生成行数: {len(sql_lines)}, 跳过空 Department ID 行: {skipped}\n"
        )
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
