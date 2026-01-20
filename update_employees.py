import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

def select_file():
    file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json")],
        title="选择 JSON 文件"
    )
    if file_path:
        generate_sql(file_path)

def clean_value(value):
    """统一处理NULL和空字符串"""
    if value is None:
        return None
    s = str(value).strip()
    if s.upper() == "NULL" or s == "":
        return None
    return s

def process_phone(phone):
    """处理手机号，保证 +968 开头且长度大于8"""
    phone = clean_value(phone)
    if not phone:
        return None
    s = phone.strip()
    if s.startswith("968"):
        s = "+" + s
    elif s.startswith("+968"):
        s = s
    else:
        s = "+968" + s
    return s if len(s) > 4 else None  # 至少保留+968+后面数字

def generate_sql(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        sql_statements = []

        # 先处理user_profile表
        for item in data:
            civil_id = clean_value(item.get("Civil Number"))
            if not civil_id:
                continue  # 忽略没有civil_id的记录

            updates = []
            # title
            title = clean_value(item.get("Job Title (EN)"))
            if title:
                updates.append(f"title = '{title.replace('\'','\'\'')}'")
            # title_ar
            title_ar = clean_value(item.get("Job Title (AR)"))
            if title_ar:
                updates.append(f"title_ar = '{title_ar.replace('\'','\'\'')}'")
            # full_name
            full_name = clean_value(item.get("enFullName"))
            if full_name:
                updates.append(f"full_name = '{full_name.replace('\'','\'\'')}'")
            # full_name_ar
            full_name_ar = clean_value(item.get("arFullName"))
            if full_name_ar:
                updates.append(f"full_name_ar = '{full_name_ar.replace('\'','\'\'')}'")
            # phone_mobile
            phone = process_phone(item.get("ContactNumber"))
            if phone:
                updates.append(f"phone_mobile = '{phone}'")
            # email
            email = clean_value(item.get("Email (@mafwr.gov.om)"))
            if email:
                updates.append(f"email = '{email.lower().replace('\'','\'\'')}'")  # 转小写

            # subject
            subject = f"{civil_id}"  # 假设subject可以用civil_id填充，也可改为其他唯一标识

            if updates:
                sql = f"""-- 更新 user_profile: civil_id={civil_id}
UPDATE user_profile
SET {', '.join(updates)}
WHERE civil_id = '{civil_id}';"""
                sql_statements.append(sql)

            # 将subject存储到item里，用于org_chart更新
            item['_subject'] = subject

        # 处理org_chart表
        dept_map = {}
        for item in data:
            dept_id = clean_value(item.get("Department ID"))
            if not dept_id:
                continue
            dept_id = dept_id.upper()  # 转大写
            subject = item.get('_subject')
            if not subject:
                continue
            if dept_id not in dept_map:
                dept_map[dept_id] = []
            dept_map[dept_id].append(subject)

        for dept_id, subjects in dept_map.items():
            # 使用 || 合并jsonb数组，保留原数据
            sql = f"""-- 更新 org_chart: employee_position_number={dept_id}
UPDATE org_chart
SET employees = (COALESCE(employees, '[]'::jsonb) || '[{', '.join(f'"{s}"' for s in subjects)}]'::jsonb)
WHERE employee_position_number = '{dept_id}';"""
            sql_statements.append(sql)

        full_sql = "\n\n".join(sql_statements)
        text_preview.delete(1.0, tk.END)
        text_preview.insert(tk.END, full_sql)
    except Exception as e:
        messagebox.showerror("错误", str(e))

def save_sql():
    sql_content = text_preview.get(1.0, tk.END).strip()
    if not sql_content:
        messagebox.showwarning("警告", "没有 SQL 内容可保存")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".sql",
        filetypes=[("SQL files", "*.sql")],
        title="保存 SQL 文件"
    )
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(sql_content)
        messagebox.showinfo("成功", f"SQL 文件已保存到：{file_path}")

# --- Tkinter 界面 ---
root = tk.Tk()
root.title("JSON 导入 user_profile & org_chart 工具")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack(fill=tk.BOTH, expand=True)

btn_select = tk.Button(frame, text="选择 JSON 文件", command=select_file)
btn_select.pack(fill=tk.X, pady=5)

text_preview = scrolledtext.ScrolledText(frame, height=25)
text_preview.pack(fill=tk.BOTH, expand=True, pady=5)

btn_save = tk.Button(frame, text="保存 SQL 文件", command=save_sql)
btn_save.pack(fill=tk.X, pady=5)

root.mainloop()

