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
            text="Generate Committee Codes",
            state=tk.DISABLED,
            command=self.generate_code_with_save,
            takefocus=True,
        )
        self.generate_btn.pack(pady=10)

        # ---- OUTPUT ----
        tk.Label(self, text="Generated Postgres Struct And Codes").pack(
            anchor=tk.W, padx=10
        )
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

    def snake_file(self, table):
        return table.lower()

    def sql_update_set(self, columns, pk):
        parts = []
        idx = 1
        for c in columns:
            if c["column_name"] == pk:
                continue
            parts.append(f"{c['column_name']} = ${idx}")
            idx += 1
        return ",\n\t\t\t".join(parts)

    def sql_update_args(self, columns, pk):
        args = []
        for c in columns:
            if c["column_name"] != pk:
                args.append(f"i.{self.camel_case(c['column_name'])}")
        args.append(f"i.{self.camel_case(pk)}")
        return ",\n\t\t".join(args)

    def detect_pk(self, columns):
        for c in columns:
            if c["column_name"] == "id":
                return "id"
        return columns[0]["column_name"]

    def generate_code_with_save(self):
        import re

        table = self.selected_table.get()
        if not table:
            messagebox.showerror("Error", "No table selected")
            return

        base_dir = filedialog.askdirectory(title="Select output directory")
        if not base_dir:
            return

        entity_dir = os.path.join(base_dir, "entity")
        pg_dir = os.path.join(base_dir, "postgres")
        os.makedirs(entity_dir, exist_ok=True)
        os.makedirs(pg_dir, exist_ok=True)

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

        struct_name = self.camel_case(table)
        file_name = table.lower()

        # ---------- entity struct ----------
        entity_lines = [
            "// Code generated by PgCodeGenApp. DO NOT EDIT.\n",
            "package entity\n",
            'import "time"\n',
            f"type {struct_name} struct {{",
        ]
        for c in columns:
            entity_lines.append(
                f"\t{self.camel_case(c['column_name'])} "
                f"{self.postgres_to_go(c['data_type'], c['is_nullable'], c['column_default'])} "
                f'`json:"{c["column_name"]}"`'
            )
        entity_lines.append("}\n")

        with open(os.path.join(entity_dir, f"{file_name}.go"), "w") as f:
            f.write("\n".join(entity_lines))

        # ---------- postgres CRUD code ----------
        # 主键推测
        pk_col = None
        for c in columns:
            if c.get("column_default") and "nextval" in str(c.get("column_default")):
                pk_col = c["column_name"]
                break
        if not pk_col:
            pk_col = columns[0]["column_name"]

        # 小驼峰字段加双引号
        def is_camel_case(name):
            return re.match(r"[a-z]+[A-Z]", name) is not None

        def sql_col_name(col):
            return f'"{col}"' if is_camel_case(col) else col

        col_names_sql = ", ".join([sql_col_name(c["column_name"]) for c in columns])
        scan_args = ", ".join(
            [f"&i.{self.camel_case(c['column_name'])}" for c in columns]
        )

        insert_cols = [
            sql_col_name(c["column_name"])
            for c in columns
            if c["column_name"] != pk_col
        ]
        insert_placeholders = [f"${i + 1}" for i in range(len(insert_cols))]
        insert_args = [
            f"i.{self.camel_case(c['column_name'])}"
            for c in columns
            if c["column_name"] != pk_col
        ]

        update_set = [
            f"{sql_col_name(c['column_name'])} = ${i + 1}"
            for i, c in enumerate(columns)
            if c["column_name"] != pk_col
        ]
        update_args = [
            f"i.{self.camel_case(c['column_name'])}"
            for c in columns
            if c["column_name"] != pk_col
        ]
        update_args.append(f"i.{self.camel_case(pk_col)}")

        # helper: 拼接最终 SQL
        def final_sql_template(sql_str, args):
            parts = []
            for a in args:
                if isinstance(a, str):
                    # 先处理单引号转义
                    escaped = a.replace("'", "''")
                    parts.append("'" + escaped + "'")
                elif isinstance(a, bool):
                    parts.append("TRUE" if a else "FALSE")
                else:
                    parts.append(str(a))
            # 替换 $1, $2 ...
            for idx, val in enumerate(parts):
                sql_str = sql_str.replace(f"${idx + 1}", val, 1)
            return sql_str

        pg_code = f"""
    // Code generated by PgCodeGenApp. DO NOT EDIT.

    package postgres

    import (
        "context"
        "database/sql"
        "fmt"
        "log/slog"

        "your_module/entity"
        "your_module/storage"
    )

    // Create{struct_name} creates a new record in {table}.
    // Demo:
    //    i := &entity.{struct_name}{{...}}
    //    err := Create{struct_name}(ctx, ses, i)
    func Create{struct_name}(ctx context.Context, ses storage.Session, i *entity.{struct_name}) error {{
        sqlStr := `
    INSERT INTO "{table}" ({", ".join(insert_cols)})
    VALUES ({", ".join(insert_placeholders)})
    RETURNING {sql_col_name(pk_col)}
    `
        args := []any{{{", ".join(insert_args)}}}
        finalSQL := `{final_sql_template('INSERT INTO "{table}" (' + ", ".join(insert_cols) + ") VALUES (" + ", ".join(insert_placeholders) + ") RETURNING " + sql_col_name(pk_col), insert_args)}`
        slog.Info("Create SQL:", "sql", finalSQL)
        return ses.QueryRow(sqlStr, args...).Scan(&i.{self.camel_case(pk_col)})
    }}

    // Update{struct_name} updates a record in {table} by primary key.
    // Demo:
    //    i := &entity.{struct_name}{{...}}
    //    err := Update{struct_name}(ctx, ses, i)
    func Update{struct_name}(ctx context.Context, ses storage.Session, i *entity.{struct_name}) error {{
        sqlStr := `
    UPDATE "{table}"
    SET {", ".join(update_set)}
    WHERE {sql_col_name(pk_col)} = ${len(update_args)}
    `
        args := []any{{{", ".join(update_args)}}}
        finalSQL := `{final_sql_template('UPDATE "{table}" SET ' + ", ".join(update_set) + " WHERE " + sql_col_name(pk_col) + " = $" + str(len(update_args)), update_args)}`
        slog.Info("Update SQL:", "sql", finalSQL)
        _, err := ses.Exec(sqlStr, args...)
        if err != nil {{
            slog.Error("Update error:", "sql", finalSQL, "err", err)
        }}
        return err
    }}

    // Delete{struct_name}ByID deletes a record by primary key.
    // Demo:
    //    err := Delete{struct_name}ByID(ctx, ses, id)
    func Delete{struct_name}ByID(ctx context.Context, ses storage.Session, id any) error {{
        sqlStr := `DELETE FROM "{table}" WHERE {sql_col_name(pk_col)} = $1`
        finalSQL := `{final_sql_template('DELETE FROM "{table}" WHERE ' + sql_col_name(pk_col) + " = $1", ["id"])}`
        slog.Info("Delete SQL:", "sql", finalSQL)
        _, err := ses.Exec(sqlStr, id)
        if err != nil {{
            slog.Error("Delete error:", "sql", finalSQL, "err", err)
        }}
        return err
    }}

    // Get{struct_name}ById retrieves a record by primary key.
    // Demo:
    //    obj, err := Get{struct_name}ById(ctx, ses, id)
    func Get{struct_name}ById(ctx context.Context, ses storage.Session, id any) (i *entity.{struct_name}, err error) {{
        sqlStr := fmt.Sprintf("SELECT {col_names_sql} FROM {table} WHERE {sql_col_name(pk_col)} = $1")
        finalSQL := fmt.Sprintf(sqlStr, id)
        slog.Info("GetById SQL:", "sql", finalSQL)
        i = &entity.{struct_name}{{}}
        err = ses.QueryRow(sqlStr, id).Scan({scan_args})
        if err != nil && err != sql.ErrNoRows {{
            slog.Error("GetById error:", "sql", finalSQL, "err", err)
        }}
        return
    }}

    // List{struct_name} lists records with optional condition, order, limit and offset.
    // Demo:
    //    list, total, err := List{struct_name}(ctx, ses, "status = $1", []any{{1}}, "ORDER BY createdAt DESC", 10, 0)
    func List{struct_name}(ctx context.Context, ses storage.Session, cond string, condArgs []any, order string, limit, offset int64) (list []*entity.{struct_name}, total int64, err error) {{
        whereSQL := ""
        args := condArgs
        if cond != "" {{
            whereSQL = " WHERE " + cond
        }}

        if limit > 0 {{
            countSQL := fmt.Sprintf("SELECT COUNT(1) FROM {table}%s", whereSQL)
            finalCountSQL := countSQL
            slog.Info("Count SQL:", "sql", finalCountSQL)
            if err = ses.QueryRow(countSQL, args...).Scan(&total); err != nil {{
                slog.Error("Count error:", "sql", finalCountSQL, "err", err)
                return
            }}
        }}

        sqlStr := fmt.Sprintf("SELECT {col_names_sql} FROM {table}%s", whereSQL)
        if order != "" {{
            sqlStr += " " + order
        }}
        if limit > 0 {{
            sqlStr += fmt.Sprintf(" OFFSET $%d LIMIT $%d", len(args)+1, len(args)+2)
            args = append(args, offset, limit)
        }}

        finalSQL := sqlStr
        for idx, a := range args {{
            val := fmt.Sprintf("%v", a)
            if s, ok := a.(string); ok {{
                val = "'" + strings.ReplaceAll(s, "'", "''") + "'"
            }} else if b, ok := a.(bool); ok {{
                if b {{ val = "TRUE" }} else {{ val = "FALSE" }}
            }}
            finalSQL = strings.Replace(finalSQL, fmt.Sprintf("${{}}", idx+1), val, 1)
        }}
        slog.Info("List SQL:", "sql", finalSQL)

        rows, err := ses.Query(sqlStr, args...)
        if err != nil {{
            slog.Error("List query error:", "sql", finalSQL, "err", err)
            return
        }}
        defer rows.Close()

        for rows.Next() {{
            var i entity.{struct_name}
            if err = rows.Scan({scan_args}); err != nil {{
                slog.Error("Scan error:", "err", err)
                return
            }}
            list = append(list, &i)
        }}

        if limit == 0 {{
            total = int64(len(list))
        }}
        return
    }}

    // Upsert{struct_name} inserts a new record if not exist, otherwise updates.
    // Demo:
    //    i := &entity.{struct_name}{{...}}
    //    err := Upsert{struct_name}(ctx, ses, "status = $1", []any{{1}}, i)
    func Upsert{struct_name}(ctx context.Context, ses storage.Session, cond string, condArgs []any, i *entity.{struct_name}) error {{
        list, _, err := List{struct_name}(ctx, ses, cond, condArgs, "", 1, 0)
        if err != nil {{
            return err
        }}
        if len(list) == 0 {{
            return Create{struct_name}(ctx, ses, i)
        }}
        i.{self.camel_case(pk_col)} = list[0].{self.camel_case(pk_col)}
        return Update{struct_name}(ctx, ses, i)
    }}
    """

        with open(os.path.join(pg_dir, f"{file_name}.go"), "w") as f:
            f.write(pg_code)

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, pg_code)
        messagebox.showinfo(
            "Success", "Postgres CRUD + Upsert + GetById code generated successfully."
        )

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

    def _bind_enter_buttons(self):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Button):
                widget.bind("<Return>", lambda e, w=widget: w.invoke())
            elif isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Button):
                        child.bind("<Return>", lambda e, w=child: w.invoke())

    def _set_tab_order(self):
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

        self.connect_btn.focus_set()


if __name__ == "__main__":
    app = PgCodeGenApp()
    app.mainloop()
