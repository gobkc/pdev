import json
import tkinter as tk
from tkinter import messagebox


def infer_go_type(value, struct_defs, struct_name_prefix, struct_counter):
    """
    根据 Python 的值推断对应的 Go 类型。
    struct_defs: 用于收集生成的 struct 定义
    struct_name_prefix: 用于命名子 struct 的前缀
    struct_counter: 用于给子 struct 编号，避免重名（用列表包一层以便引用修改）
    """
    if value is None:
        return "interface{}"

    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int) or isinstance(value, float):
        return "float64"

    if isinstance(value, str):
        return "string"

    if isinstance(value, list):
        if not value:
            return "[]interface{}"
        elem_type = infer_go_type(value[0], struct_defs, struct_name_prefix, struct_counter)
        return "[]" + elem_type

    if isinstance(value, dict):
        struct_counter[0] += 1
        struct_name = f"{struct_name_prefix}{struct_counter[0]}"

        fields = []
        for k, v in value.items():
            go_field_name = to_go_field_name(k)
            field_type = infer_go_type(v, struct_defs, struct_name, struct_counter)
            json_tag = k
            fields.append(f"\t{go_field_name} {field_type} `json:\"{json_tag}\"`")

        struct_def = f"type {struct_name} struct {{\n" + "\n".join(fields) + "\n}"
        struct_defs.append(struct_def)
        return struct_name

    return "interface{}"


def to_go_field_name(key: str) -> str:
    import re
    parts = re.split(r'[^0-9a-zA-Z]+', key)
    parts = [p for p in parts if p]
    if not parts:
        return "Field"

    def upper_first(s):
        if not s:
            return s
        return s[0].upper() + s[1:]

    return "".join(upper_first(p) for p in parts)


def json_to_go_struct(json_text: str, root_struct_name: str = "Test") -> str:
    try:
        data = json.loads(json_text)
    except Exception as e:
        raise ValueError(f"JSON 解析失败: {e}")

    struct_defs = []
    struct_counter = [0]

    if isinstance(data, dict):
        fields = []
        for k, v in data.items():
            go_field_name = to_go_field_name(k)
            field_type = infer_go_type(v, struct_defs, root_struct_name, struct_counter)
            json_tag = k
            fields.append(f"\t{go_field_name} {field_type} `json:\"{json_tag}\"`")

        root_def = f"type {root_struct_name} struct {{\n" + "\n".join(fields) + "\n}"
        result_defs = [root_def] + struct_defs
        return "\n\n".join(result_defs)

    elif isinstance(data, list):
        if not data:
            return f"type {root_struct_name} []interface{{}}\n"

        first = data[0]
        elem_type = infer_go_type(first, struct_defs, root_struct_name, struct_counter)

        if not struct_defs and not isinstance(first, dict):
            return f"type {root_struct_name} []{elem_type}\n"

        if isinstance(first, dict):
            fields = []
            for k, v in first.items():
                go_field_name = to_go_field_name(k)
                field_type = infer_go_type(v, struct_defs, root_struct_name, struct_counter)
                json_tag = k
                fields.append(f"\t{go_field_name} {field_type} `json:\"{json_tag}\"`")
            elem_struct_name = root_struct_name + "Item"
            root_def = f"type {elem_struct_name} struct {{\n" + "\n".join(fields) + "\n}"
            slice_def = f"type {root_struct_name} []{elem_struct_name}"
            result_defs = [root_def, slice_def] + struct_defs
            return "\n\n".join(result_defs)

        return f"type {root_struct_name} []{elem_type}\n"

    else:
        go_type = infer_go_type(data, struct_defs, root_struct_name, struct_counter)
        return f"type {root_struct_name} {go_type}\n"


def on_convert():
    raw = text.get("1.0", tk.END).strip()
    if not raw:
        messagebox.showwarning("提示", "请先在文本框中粘贴 JSON 字符串。")
        return
    try:
        go_code = json_to_go_struct(raw, root_struct_name="Test")
    except ValueError as e:
        messagebox.showerror("错误", str(e))
        return

    text.delete("1.0", tk.END)
    text.insert(tk.END, go_code)


# ====== 快捷键处理函数 ======
def select_all(event=None):
    text.tag_add("sel", "1.0", "end-1c")
    return "break"  # 阻止默认行为


def cut_text(event=None):
    try:
        selection = text.get("sel.first", "sel.last")
    except tk.TclError:
        return "break"
    text.clipboard_clear()
    text.clipboard_append(selection)
    text.delete("sel.first", "sel.last")
    return "break"


def paste_text(event=None):
    try:
        clip = text.clipboard_get()
    except tk.TclError:
        return "break"
    text.insert(tk.INSERT, clip)
    return "break"


def main():
    global text
    root = tk.Tk()
    root.title("JSON → Go Struct (Test)")

    text = tk.Text(root, width=100, height=30, undo=True)
    text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 绑定快捷键：Ctrl+A / Ctrl+X / Ctrl+V
    text.bind("<Control-a>", select_all)
    text.bind("<Control-A>", select_all)  # 兼容大小写
    text.bind("<Control-x>", cut_text)
    text.bind("<Control-X>", cut_text)
    text.bind("<Control-v>", paste_text)
    text.bind("<Control-V>", paste_text)

    btn = tk.Button(root, text="转换为 Go Struct (Test)", command=on_convert)
    btn.pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()

