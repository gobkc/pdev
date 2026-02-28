import tkinter as tk

from tksheet import Sheet


def create_tksheet():
    root = tk.Tk()
    root.title("tksheet 高级表格")

    sheet = Sheet(root)
    sheet.pack(fill="both", expand=True)

    # 设置表头
    sheet.headers(["姓名", "年龄", "邮箱", "电话"])

    # 设置数据
    data = [
        ["张三", "25", "zhangsan@example.com", "13800138001"],
        ["李四", "30", "lisi@example.com", "13900139001"],
        ["王五", "28", "wangwu@example.com", "13700137001"],
    ]
    sheet.set_sheet_data(data)

    # 启用编辑功能
    sheet.enable_bindings()

    root.mainloop()


create_tksheet()
