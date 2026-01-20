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

def generate_sql(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        sql_statements = []

        for item in data:
            iso_code = item['ISO_CODE']
            parent_iso_code = iso_code[:2]
            name_ar = item['NAME_AR'].replace("'", "''")
            name_en = item['NAME_EN'].replace("'", "''")

            sql = f"""-- ISO_CODE: {iso_code}
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM org_chart_locations WHERE iso_code = '{iso_code}') THEN
        UPDATE org_chart_locations
        SET name_ar = '{name_ar}',
            name_en = '{name_en}',
            parent_iso_code = '{parent_iso_code}',
            level = 2
        WHERE iso_code = '{iso_code}';
    ELSE
        INSERT INTO org_chart_locations (name_ar, name_en, iso_code, parent_iso_code, level)
        VALUES ('{name_ar}', '{name_en}', '{iso_code}', '{parent_iso_code}', 3);
    END IF;
END $$;
"""
            sql_statements.append(sql)

        full_sql = "\n".join(sql_statements)
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
root.title("JSON 转 SQL 工具")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack(fill=tk.BOTH, expand=True)

btn_select = tk.Button(frame, text="选择 JSON 文件", command=select_file)
btn_select.pack(fill=tk.X, pady=5)

text_preview = scrolledtext.ScrolledText(frame, height=20)
text_preview.pack(fill=tk.BOTH, expand=True, pady=5)

btn_save = tk.Button(frame, text="保存 SQL 文件", command=save_sql)
btn_save.pack(fill=tk.X, pady=5)

root.mainloop()

