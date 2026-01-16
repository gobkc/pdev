import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ------------------------
# 工具函数
# ------------------------
def clean_value(value):
    """NULL / 空字符串统一返回 None"""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.upper() == "NULL":
        return None
    return s

def sql_escape(value: str) -> str:
    """SQL 单引号转义"""
    return value.replace("'", "''")

def process_phone(phone):
    """
    规则：
    - NULL / 空 → 不更新
    - 968开头 → +968xxxx
    - 非968 → +968xxxx
    - 最终必须 +968 开头且长度 > 8
    """
    phone = clean_value(phone)
    if not phone:
        return None

    p = phone.strip()

    if p.startswith("+968"):
        pass
    elif p.startswith("968"):
        p = "+" + p
    else:
        p = "+968" + p

    if len(p) <= 8:
        return None

    return p

# ------------------------
# 主逻辑
# ------------------------
def select_file():
    path = filedialog.askopenfilename(
        title="选择 JSON 文件",
        filetypes=[("JSON files", "*.json")]
    )
    if path:
        generate_sql(path)

def generate_sql(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sql_blocks = []

        # ------------------------
        # user_profile 更新
        # ------------------------
        for item in data:
            civil_id = clean_value(item.get("Civil Number"))
            if not civil_id:
                continue

            updates = []

            title = clean_value(item.get("Job Title (EN)"))
            if title:
                updates.append(f"title = '{sql_escape(title)}'")

            title_ar = clean_value(item.get("Job Title (AR)"))
            if title_ar:
                updates.append(f"title_ar = '{sql_escape(title_ar)}'")

            full_name = clean_value(item.get("enFullName"))
            if full_name:
                updates.append(f"full_name = '{sql_escape(full_name)}'")

            full_name_ar = clean_value(item.get("arFullName"))
            if full_name_ar:
                updates.append(f"full_name_ar = '{sql_escape(full_name_ar)}'")

            phone = process_phone(item.get("ContactNumber"))
            if phone:
                updates.append(f"phone_mobile = '{phone}'")

            email = clean_value(item.get("Email (@mafwr.gov.om)"))
            if email:
                updates.append(f"email = '{sql_escape(email.lower())}'")

            if updates:
                sql_blocks.append(
                    f"""-- user_profile | civil_id = {civil_id}
UPDATE user_profile
SET {", ".join(updates)}
WHERE civil_id = '{civil_id}';
"""
                )

        # ------------------------
        # org_chart employees 更新（去重 & subject 来自 user_profile）
        # ------------------------
        dept_civil_map = {}

        for item in data:
            civil_id = clean_value(item.get("Civil Number"))
            dept_id = clean_value(item.get("Department ID"))

            if not civil_id or not dept_id:
                continue

            dept_id = dept_id.upper()
            dept_civil_map.setdefault(dept_id, set()).add(civil_id)

        for dept_id, civil_ids in dept_civil_map.items():
            civil_list = ", ".join(f"'{sql_escape(cid)}'" for cid in civil_ids)

            sql_blocks.append(
                f"""-- org_chart | employee_position_number = {dept_id}
UPDATE org_chart
SET employees = COALESCE((
    SELECT jsonb_agg(DISTINCT s.subject)
    FROM (
        SELECT jsonb_array_elements_text(COALESCE(employees, '[]'::jsonb)) AS subject
        FROM org_chart
        WHERE employee_position_number = '{dept_id}'
    ) e
    FULL OUTER JOIN (
        SELECT subject
        FROM user_profile
        WHERE civil_id IN ({civil_list})
          AND subject IS NOT NULL
    ) s USING (subject)
), '[]'::jsonb)
WHERE employee_position_number = '{dept_id}';
"""
            )

        final_sql = "\n".join(sql_blocks)

        text_preview.delete(1.0, tk.END)
        text_preview.insert(tk.END, final_sql)

    except Exception as e:
        messagebox.showerror("错误", str(e))

def save_sql():
    content = text_preview.get(1.0, tk.END).strip()
    if not content:
        messagebox.showwarning("提示", "没有可保存的 SQL")
        return

    path = filedialog.asksaveasfilename(
        title="保存 SQL 文件",
        defaultextension=".sql",
        filetypes=[("SQL files", "*.sql")]
    )
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("成功", f"SQL 已保存：\n{path}")

# ------------------------
# Tk UI
# ------------------------
root = tk.Tk()
root.title("JSON → user_profile / org_chart SQL 生成器")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack(fill=tk.BOTH, expand=True)

tk.Button(frame, text="选择 JSON 文件", command=select_file).pack(fill=tk.X, pady=5)

text_preview = scrolledtext.ScrolledText(frame, height=28)
text_preview.pack(fill=tk.BOTH, expand=True, pady=5)

tk.Button(frame, text="保存 SQL 文件", command=save_sql).pack(fill=tk.X, pady=5)

root.mainloop()

