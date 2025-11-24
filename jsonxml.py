#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import xml.dom.minidom

# --- 格式化函数 ---
def format_text():
    text = text_box.get("1.0", tk.END).strip()
    if not text:
        messagebox.showerror("错误", "请输入 JSON 或 XML 字符串")
        return

    global current_format
    try:
        # 尝试格式化为 JSON
        parsed_json = json.loads(text)
        formatted = json.dumps(parsed_json, indent=4, ensure_ascii=False)
        current_format = "json"
        btn_convert.config(text="转换为 XML")
    except json.JSONDecodeError:
        try:
            # 尝试格式化为 XML
            dom = xml.dom.minidom.parseString(text)
            formatted = dom.toprettyxml(indent="    ")
            # 去掉多余空行
            formatted = "\n".join([line for line in formatted.splitlines() if line.strip()])
            current_format = "xml"
            btn_convert.config(text="转换为 JSON")
        except Exception as e:
            messagebox.showerror("错误", f"解析失败: {str(e)}")
            return

    text_box.delete("1.0", tk.END)
    text_box.insert(tk.END, formatted)

# --- 清空函数 ---
def clear_text():
    text_box.delete("1.0", tk.END)

# --- JSON <-> XML 转换 ---
def convert_text():
    text = text_box.get("1.0", tk.END).strip()
    if not text:
        messagebox.showerror("错误", "文本为空")
        return

    try:
        global current_format
        if current_format == "json":
            # JSON -> XML
            parsed_json = json.loads(text)
            xml_str = dict_to_xml_str(parsed_json)
            # 格式化 XML
            dom = xml.dom.minidom.parseString(xml_str)
            formatted = "\n".join([line for line in dom.toprettyxml(indent="    ").splitlines() if line.strip()])
            text_box.delete("1.0", tk.END)
            text_box.insert(tk.END, formatted)
            current_format = "xml"
            btn_convert.config(text="转换为 JSON")
        elif current_format == "xml":
            # XML -> JSON
            dom = xml.dom.minidom.parseString(text)
            json_obj = xml_to_dict(dom.documentElement)
            formatted = json.dumps(json_obj, indent=4, ensure_ascii=False)
            text_box.delete("1.0", tk.END)
            text_box.insert(tk.END, formatted)
            current_format = "json"
            btn_convert.config(text="转换为 XML")
        else:
            messagebox.showerror("错误", "无法识别文本格式")
    except Exception as e:
        messagebox.showerror("错误", f"转换失败: {str(e)}")

# --- 简单 JSON -> XML 转换 ---
def dict_to_xml_str(d, root_tag="root"):
    def to_xml(d, indent=""):
        xml_str = ""
        for k, v in d.items():
            k = str(k)
            if isinstance(v, dict):
                xml_str += f"{indent}<{k}>\n{to_xml(v, indent + '    ')}{indent}</{k}>\n"
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        xml_str += f"{indent}<{k}>\n{to_xml(item, indent + '    ')}{indent}</{k}>\n"
                    else:
                        xml_str += f"{indent}<{k}>{item}</{k}>\n"
            else:
                xml_str += f"{indent}<{k}>{v}</{k}>\n"
        return xml_str
    return f"<{root_tag}>\n{to_xml(d)}</{root_tag}>"

# --- 简单 XML -> JSON 转换 ---
def xml_to_dict(elem):
    d = {}
    children = list(elem.childNodes)
    for child in children:
        if child.nodeType == child.TEXT_NODE:
            if child.data.strip():
                return child.data.strip()
        elif child.nodeType == child.ELEMENT_NODE:
            val = xml_to_dict(child)
            if child.tagName in d:
                if isinstance(d[child.tagName], list):
                    d[child.tagName].append(val)
                else:
                    d[child.tagName] = [d[child.tagName], val]
            else:
                d[child.tagName] = val
    return d

# --- GUI ---
root = tk.Tk()
root.title("JSON/XML 格式化 & 转换")
root.geometry("800x600")

style = ttk.Style(root)
style.theme_use("clam")

# 按钮框
frame_btns = ttk.Frame(root, padding=5)
frame_btns.pack(fill=tk.X)

btn_format = ttk.Button(frame_btns, text="格式化", command=format_text)
btn_format.pack(side=tk.LEFT, padx=5)

btn_convert = ttk.Button(frame_btns, text="转换", command=convert_text)
btn_convert.pack(side=tk.LEFT, padx=5)

btn_clear = ttk.Button(frame_btns, text="清空", command=clear_text)
btn_clear.pack(side=tk.LEFT, padx=5)

# 文本框
text_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, undo=True)
text_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Ctrl+A 全选
def select_all(event=None):
    text_box.tag_add("sel", "1.0", "end")
    return "break"

text_box.bind("<Control-a>", select_all)
text_box.bind("<Control-A>", select_all)

# 当前文本格式：json 或 xml
current_format = None

root.mainloop()
