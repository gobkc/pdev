import os
import textwrap
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import psycopg2
from psycopg2.extras import DictCursor

DEFAULT_DSN = "postgres://postgres:postgres@cfg-envs:5432/?sslmode=disable"


class PgCodeGenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Postgres Code Generator")
        self.geometry("750x650")

        self.conn = None
        self.databases = []
        self.tables = []

        self.selected_db = tk.StringVar()
        self.selected_table = tk.StringVar()

        self._build_ui()
        self._bind_shortcuts()
        self._bind_enter_buttons()
        self._set_tab_order()

    def _build_ui(self):
        # ---- DSN ----
        dsn_frame = tk.Frame(self)
        dsn_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(dsn_frame, text="Postgres DSN").pack(anchor=tk.W)
        self.dsn_var = tk.StringVar(value=DEFAULT_DSN)
        self.dsn_entry = tk.Entry(dsn_frame, textvariable=self.dsn_var, takefocus=True)
        self.dsn_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.connect_btn = tk.Button(
            dsn_frame, text="Connect", command=self.connect_db, takefocus=True
        )
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # ---- STATUS ----
        self.status_var = tk.StringVar(value="Not connected")
        self.status_label = tk.Label(self, textvariable=self.status_var, fg="gray")
        self.status_label.pack(anchor=tk.W, padx=10)

        # ---- SELECT DATABASE ----
        db_frame = tk.Frame(self)
        db_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(db_frame, text="SELECT DATABASE (filter)").pack(anchor=tk.W)

        self.db_filter_var = tk.StringVar()
        self.db_filter_entry = tk.Entry(
            db_frame, textvariable=self.db_filter_var, takefocus=True
        )
        self.db_filter_entry.pack(fill=tk.X)
        self.db_filter_var.trace_add("write", lambda *args: self.filter_databases())

        self.db_combobox = ttk.Combobox(
            db_frame, textvariable=self.selected_db, state="readonly", takefocus=True
        )
        self.db_combobox.pack(fill=tk.X)
        self.db_combobox.bind("<<ComboboxSelected>>", self.on_db_selected)

        # ---- TABLE FILTER + COMBOBOX ----
        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(table_frame, text="FILTER TABLES").pack(anchor=tk.W)

        self.table_filter_var = tk.StringVar()
        self.table_filter_entry = tk.Entry(
            table_frame, textvariable=self.table_filter_var, takefocus=True
        )
        self.table_filter_entry.pack(fill=tk.X)
        self.table_filter_var.trace_add("write", lambda *args: self.filter_tables())

        tk.Label(table_frame, text="SELECT TABLE").pack(anchor=tk.W)
        self.table_combobox = ttk.Combobox(
            table_frame,
            textvariable=self.selected_table,
            state="readonly",
            takefocus=True,
        )
        self.table_combobox.pack(fill=tk.X)
        self.table_combobox.bind("<<ComboboxSelected>>", self.on_table_selected)

        # ---- GENERATE BUTTON ----
        self.generate_btn = tk.Button(
            self,
            text="Generate GORM",
            state=tk.DISABLED,
            command=self.generate_gorm_with_save,
            takefocus=True,
        )
        self.generate_btn.pack(pady=10)

        # ---- OUTPUT ----
        tk.Label(self, text="Generated GORM Struct").pack(anchor=tk.W, padx=10)
        self.output_text = tk.Text(self, height=20, takefocus=True)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # ================= DB Logic =================
    def connect_db(self):
        dsn = self.dsn_var.get().strip()
        if not dsn:
            messagebox.showerror("Error", "DSN is empty")
            return
        try:
            self.conn = psycopg2.connect(dsn)
            self.conn.autocommit = True
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            self.status_var.set("Connected successfully")
            self.status_label.config(fg="green")
            self.load_databases()
        except Exception as e:
            self.conn = None
            self.status_var.set("Connection failed")
            self.status_label.config(fg="red")
            messagebox.showerror("Connection Error", str(e))

    def load_databases(self):
        sql = "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            self.databases = [row[0] for row in cur.fetchall()]
        self.update_db_combobox(self.databases)

    def update_db_combobox(self, db_list):
        self.db_combobox["values"] = db_list
        if db_list:
            self.db_combobox.current(0)
            self.on_db_selected(None)
        else:
            self.selected_db.set("")
            self.table_combobox["values"] = []
            self.selected_table.set("")
            self.generate_btn.config(state=tk.DISABLED)

    def filter_databases(self):
        text = self.db_filter_var.get().lower()
        filtered = [db for db in self.databases if text in db.lower()]
        self.update_db_combobox(filtered)

    def on_db_selected(self, event):
        db_name = self.selected_db.get()
        if db_name:
            self.load_tables(db_name)

    def load_tables(self, db_name):
        dsn = self.dsn_var.get().strip()
        try:
            if self.conn:
                self.conn.close()
            self.conn = psycopg2.connect(dsn + f"&dbname={db_name}")
            self.conn.autocommit = True

            sql = "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            with self.conn.cursor() as cur:
                cur.execute(sql)
                self.tables = [row[0] for row in cur.fetchall()]
            self.update_table_combobox(self.tables)
        except Exception as e:
            messagebox.showerror("Table Load Error", str(e))

    def update_table_combobox(self, table_list):
        self.table_combobox["values"] = table_list
        if table_list:
            self.table_combobox.current(0)
            self.on_table_selected(None)
        else:
            self.selected_table.set("")
            self.generate_btn.config(state=tk.DISABLED)

    def filter_tables(self):
        text = self.table_filter_var.get().lower()
        filtered = [t for t in self.tables if text in t.lower()]
        self.update_table_combobox(filtered)

    def on_table_selected(self, event):
        self.generate_btn.config(
            state=tk.NORMAL if self.selected_table.get() else tk.DISABLED
        )

    # ================= GORM Generation =================
    import os
    import textwrap
    from tkinter import filedialog

    def generate_gorm_with_save(self):
        """
        生成 GORM 代码，显示在 output_text 中，并保存到用户选择的目录 (_def.go 和 _gorm.go)
        package 根据目录名自动设置，import 包含 time 和 gorm
        """
        table = self.selected_table.get()
        if not table:
            messagebox.showerror("Error", "No table selected")
            return

        # 选择目录
        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        try:
            # 获取表结构
            with self.conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position
                """,
                    (table,),
                )
                columns = cur.fetchall()
                col_names = [c["column_name"] for c in columns]
                soft_delete_field = "deleted_at" if "deleted_at" in col_names else None

            struct_name = self.camel_case(table)
            interface_name = f"I{struct_name}Repo"

            # 自动获取package名（目录名最后一部分）
            package_name = os.path.basename(os.path.normpath(output_dir))

            # ----------- Interface 定义 (_def.go) -----------
            interface_lines = [f"type {interface_name} interface {{"]
            interface_lines.append(
                f"    Create(ctx context.Context, obj *{struct_name}) error"
            )
            interface_lines.append(
                f"    Update(ctx context.Context, obj *{struct_name}) error"
            )
            interface_lines.append(f"    Delete(ctx context.Context, id any) error")
            interface_lines.append(
                f"    GetByWhere(ctx context.Context, query string, args ...any) GetByWhereResponse"
            )
            interface_lines.append(
                f"    ListByWhere(ctx context.Context, query string, args ...any, offset, limit int) ListByWhereResponse"
            )
            interface_lines.append(
                f"    GetByField(ctx context.Context, field string, value any) ([]*{struct_name}, error)"
            )
            interface_lines.append(
                f"    ListWithPagination(ctx context.Context, offset, limit int) ([]*{struct_name}, int64, error)"
            )
            interface_lines.append("}\n")

            # ----------- struct 定义 (_def.go) -----------
            struct_lines = [f"type {struct_name} struct {{"]
            for col in columns:
                go_type = self.postgres_to_go(
                    col["data_type"], col["is_nullable"], col["column_default"]
                )
                struct_lines.append(
                    f'    {self.camel_case(col["column_name"])} {go_type} `gorm:"column:{col["column_name"]}"`'
                )
            struct_lines.append("}\n")
            struct_lines.append(
                f'func ({struct_name}) TableName() string {{ return "{table}" }}\n'
            )

            # ----------- 响应对象 (_def.go) -----------
            response_structs = f"""
type GetByWhereResponse struct {{
    repo *{struct_name}Repo
    conditions []any
    row *{struct_name}
}}

func (r *GetByWhereResponse) Upsert(ctx context.Context, fn func(row *{struct_name})) {{
    if r.row != nil {{
        fn(r.row)
        r.repo.db.WithContext(ctx).Save(r.row)
    }}
}}

func (r *GetByWhereResponse) Delete(ctx context.Context) {{
    if len(r.conditions) == 0 {{
        return
    }}
    r.repo.db.WithContext(ctx).Where(r.conditions[0], r.conditions[1:]...).Delete(&{struct_name}{{}})
}}

type ListByWhereResponse struct {{
    repo *{struct_name}Repo
    conditions []any
    rows []*{struct_name}
    Total int64
}}

func (r *ListByWhereResponse) Upsert(ctx context.Context, fn func(rows []*{struct_name})) {{
    if len(r.rows) > 0 {{
        fn(r.rows)
        for _, row := range r.rows {{
            r.repo.db.WithContext(ctx).Save(row)
        }}
    }}
}}

func (r *ListByWhereResponse) Delete(ctx context.Context) {{
    if len(r.conditions) == 0 {{
        return
    }}
    r.repo.db.WithContext(ctx).Where(r.conditions[0], r.conditions[1:]...).Delete(&{struct_name}{{}})
}}
    """

            # ----------- 保存 _def.go ----------- #
            os.makedirs(output_dir, exist_ok=True)
            def_path = os.path.join(output_dir, f"{table}_def.go")
            with open(def_path, "w", encoding="utf-8") as f:
                f.write("// Code generated by PgCodeGenApp. DO NOT EDIT.\n\n")
                f.write(f"package {package_name}\n\n")
                f.write('import (\n    "context"\n    "log/slog"\n    "time"\n)\n\n')
                f.write("\n".join(interface_lines) + "\n")
                f.write("\n".join(struct_lines) + "\n")
                f.write(response_structs)

            # ----------- Repo 实现 (_gorm.go) -----------
            impl_lines = [f"type {struct_name}Repo struct {{ db *gorm.DB }}\n"]
            impl_lines.append(
                f"func New{struct_name}Repo(db *gorm.DB) *{struct_name}Repo {{ return &{struct_name}Repo{{db: db}} }}\n"
            )
            filter_line_where = "r.db.WithContext(ctx)"
            if soft_delete_field:
                filter_line_where += f'.Where("{soft_delete_field} IS NULL")'

            impl_lines.append(
                textwrap.dedent(f"""\
                func (r *{struct_name}Repo) Create(ctx context.Context, obj *{struct_name}) error {{
                    return r.db.WithContext(ctx).Create(obj).Error
                }}

                func (r *{struct_name}Repo) Update(ctx context.Context, obj *{struct_name}) error {{
                    return r.db.WithContext(ctx).Save(obj).Error
                }}

                func (r *{struct_name}Repo) Delete(ctx context.Context, id any) error {{
                    return r.db.WithContext(ctx).Delete(&{struct_name}{{}}, id).Error
                }}

                func (r *{struct_name}Repo) GetByWhere(ctx context.Context, query string, args ...any) GetByWhereResponse {{
                    var obj {struct_name}
                    err := {filter_line_where}.Where(query, args...).First(&obj).Error
                    if err != nil {{
                        slog.Error("GetByWhere failed:", err)
                        return GetByWhereResponse{{repo: r, conditions: append([]any{{query}}, args...), row: nil}}
                    }}
                    return GetByWhereResponse{{repo: r, conditions: append([]any{{query}}, args...), row: &obj}}
                }}

                func (r *{struct_name}Repo) ListByWhere(ctx context.Context, query string, args ...any, offset, limit int) ListByWhereResponse {{
                    var objs []*{struct_name}
                    var total int64
                    tx := {filter_line_where}.Where(query, args...)
                    tx.Model(&{struct_name}{{}}).Count(&total)
                    tx.Limit(limit).Offset(offset).Find(&objs)
                    return ListByWhereResponse{{repo: r, conditions: append([]any{{query}}, args...), rows: objs, Total: total}}
                }}

                func (r *{struct_name}Repo) GetByField(ctx context.Context, field string, value any) ([]*{struct_name}, error) {{
                    var objs []*{struct_name}
                    err := {filter_line_where}.Where(field, value).Find(&objs).Error
                    if err != nil {{
                        slog.Error("GetByField failed:", err)
                    }}
                    return objs, err
                }}

                func (r *{struct_name}Repo) ListWithPagination(ctx context.Context, offset, limit int) ([]*{struct_name}, int64, error) {{
                    var objs []*{struct_name}
                    var total int64
                    tx := {filter_line_where}
                    if err := tx.Model(&{struct_name}{{}}).Count(&total).Error; err != nil {{
                        return nil, 0, err
                    }}
                    if err := tx.Limit(limit).Offset(offset).Find(&objs).Error; err != nil {{
                        return nil, 0, err
                    }}
                    return objs, total, nil
                }}
            """)
            )

            gorm_path = os.path.join(output_dir, f"{table}_gorm.go")
            with open(gorm_path, "w", encoding="utf-8") as f:
                f.write("// Code generated by PgCodeGenApp. DO NOT EDIT.\n\n")
                f.write(f"package {package_name}\n\n")
                f.write(
                    'import (\n    "context"\n    "time"\n    "gorm.io/gorm"\n    "log/slog"\n)\n\n'
                )
                f.write("\n".join(impl_lines))

            # ----------- 显示在 output_text 中 ----------- #
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(
                tk.END,
                "\n".join(
                    struct_lines + [response_structs] + interface_lines + impl_lines
                ),
            )

            messagebox.showinfo("Success", f"Files saved:\n{def_path}\n{gorm_path}")

        except Exception as e:
            messagebox.showerror("Generate Error", str(e))

    def postgres_to_go(self, pg_type, is_nullable, column_default):
        mapping = {
            "integer": "int",
            "bigint": "int64",
            "smallint": "int",
            "serial": "int",
            "bigserial": "int64",
            "text": "string",
            "character varying": "string",
            "boolean": "bool",
            "timestamp without time zone": "time.Time",
            "timestamp with time zone": "time.Time",
            "date": "time.Time",
            "numeric": "float64",
            "double precision": "float64",
        }
        go_type = mapping.get(pg_type, "string")
        if is_nullable == "YES" and not column_default and go_type != "string":
            go_type = f"*{go_type}"
        return go_type

    def camel_case(self, s):
        return "".join(word.capitalize() for word in s.split("_"))

    # ================= Ctrl shortcuts =================
    def _bind_shortcuts(self):
        def bind_widget(widget):
            if isinstance(widget, tk.Text):
                widget.bind(
                    "<Control-a>",
                    lambda e: widget.tag_add("sel", "1.0", "end") or "break",
                )
                widget.bind(
                    "<Control-A>",
                    lambda e: widget.tag_add("sel", "1.0", "end") or "break",
                )
            else:
                widget.bind(
                    "<Control-a>", lambda e: widget.select_range(0, tk.END) or "break"
                )
                widget.bind(
                    "<Control-A>", lambda e: widget.select_range(0, tk.END) or "break"
                )
            widget.bind("<Control-c>", lambda e: widget.event_generate("<<Copy>>"))
            widget.bind("<Control-C>", lambda e: widget.event_generate("<<Copy>>"))
            widget.bind("<Control-x>", lambda e: widget.event_generate("<<Cut>>"))
            widget.bind("<Control-X>", lambda e: widget.event_generate("<<Cut>>"))
            widget.bind("<Control-v>", lambda e: widget.event_generate("<<Paste>>"))
            widget.bind("<Control-V>", lambda e: widget.event_generate("<<Paste>>"))

        for widget in self.winfo_children():
            if isinstance(widget, (tk.Entry, tk.Text)):
                bind_widget(widget)
            elif isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, (tk.Entry, tk.Text)):
                        bind_widget(child)

    # ================= Enter triggers for buttons =================
    def _bind_enter_buttons(self):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Button):
                widget.bind("<Return>", lambda e, w=widget: w.invoke())
            elif isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Button):
                        child.bind("<Return>", lambda e, w=child: w.invoke())

    # ================= Custom Tab Order =================
    def _set_tab_order(self):
        # 按照需求设置Tab顺序: connect_btn -> db_filter_entry -> table_filter_entry -> generate_btn -> output_text
        order = [
            self.connect_btn,
            self.db_filter_entry,
            self.table_filter_entry,
            self.generate_btn,
            self.output_text,
        ]
        for i, widget in enumerate(order):
            next_widget = order[(i + 1) % len(order)]
            widget.tk_focusNext = lambda w=next_widget: w

        # 焦点初始在Connect按钮
        self.connect_btn.focus_set()


if __name__ == "__main__":
    app = PgCodeGenApp()
    app.mainloop()
