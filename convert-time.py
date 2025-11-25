#!/usr/bin/env python3
"""Timestamp <-> Datetime Converter (Tkinter)

Single-file Python3 + Tkinter app.
Features:
- Convert timestamp -> human-readable time (detects seconds/ms/us/ns by digit count)
- Convert human-readable time -> timestamp (outputs seconds/ms/us/ns)
- Supports custom datetime format (default: %Y-%m-%d %H:%M:%S)
- Choose timezone for conversions: Local or UTC
- Copy result to clipboard

Run: python3 timestamp_converter.py
"""

import re
import sys
import time
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, messagebox

# --- Utilities ---

def detect_scale_from_digits(s: str) -> int:
    """Guess scale factor based on how many digits are in the numeric timestamp string.
    Returns divisor to convert the integer-like timestamp to seconds (i.e. factor).
    If timestamp has 10 digits -> returns 1 (seconds).
    11-13 -> 1e3 (milliseconds), 14-16 -> 1e6 (microseconds), >=17 -> 1e9 (nanoseconds).
    """
    digits = ''.join(ch for ch in s if ch.isdigit())
    n = len(digits)
    if n <= 10:
        return 1
    if n <= 13:
        return 10 ** 3
    if n <= 16:
        return 10 ** 6
    return 10 ** 9


def timestamp_to_dt(ts_input: str, tz: str = 'Local') -> datetime:
    """Convert timestamp string (int or float, any length) to datetime object.
    tz: 'Local' or 'UTC'
    """
    s = ts_input.strip()
    if not s:
        raise ValueError('空输入')

    # Accept numeric forms like 1600000000 or 1600000000000 or float like 1600000000.123
    # Try parse to float first
    try:
        ts_float = float(s)
    except ValueError:
        # allow thousands separators like 1_600_000_000
        s2 = re.sub(r"[^0-9.]", "", s)
        if not s2:
            raise
        ts_float = float(s2)

    # Decide scale using digits in the input (good heuristic for integers)
    scale = detect_scale_from_digits(s)
    seconds = ts_float / scale

    if tz == 'UTC':
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    else:
        # local timezone
        return datetime.fromtimestamp(seconds)


def dt_to_timestamp(dt: datetime, out_scale: str = 'seconds', tz: str = 'Local') -> int:
    """Convert datetime to integer timestamp in requested unit.
    out_scale: 'seconds'|'milliseconds'|'microseconds'|'nanoseconds'
    tz: if 'UTC', interpret dt as UTC; otherwise as local time.
    """
    if tz == 'UTC':
        # if dt has tzinfo, convert; else assume naive is UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    else:
        # local: if dt is timezone-aware, convert to local timestamp via timestamp()
        if dt.tzinfo is not None:
            dt = dt.astimezone()

    seconds = dt.timestamp()

    if out_scale == 'seconds':
        return int(seconds)
    if out_scale == 'milliseconds':
        return int(seconds * 1_000)
    if out_scale == 'microseconds':
        return int(seconds * 1_000_000)
    if out_scale == 'nanoseconds':
        return int(seconds * 1_000_000_000)
    raise ValueError('未知输出单位')


# --- GUI ---

class TimestampConverter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('时间戳转换器')
        self.geometry('720x360')
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        pad = 8
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill=tk.BOTH, expand=True)

        # Mode selection
        mode_lbl = ttk.Label(frm, text='模式：')
        mode_lbl.grid(row=0, column=0, sticky='w')

        self.mode = tk.StringVar(value='ts2time')
        rb1 = ttk.Radiobutton(frm, text='时间戳 -> 时间', variable=self.mode, value='ts2time', command=self._on_mode_change)
        rb2 = ttk.Radiobutton(frm, text='时间 -> 时间戳', variable=self.mode, value='time2ts', command=self._on_mode_change)
        rb1.grid(row=0, column=1, sticky='w')
        rb2.grid(row=0, column=2, sticky='w')

        # Input
        in_lbl = ttk.Label(frm, text='输入：')
        in_lbl.grid(row=1, column=0, sticky='nw', pady=(6, 0))
        self.input_text = tk.Text(frm, height=3, width=70)
        self.input_text.grid(row=1, column=1, columnspan=4, pady=(6, 0))

        # For time->timestamp, format and timezone
        fmt_lbl = ttk.Label(frm, text='时间格式：')
        fmt_lbl.grid(row=2, column=0, sticky='w', pady=(10, 0))
        self.format_var = tk.StringVar(value='%Y-%m-%d %H:%M:%S')
        self.format_entry = ttk.Entry(frm, textvariable=self.format_var, width=32)
        self.format_entry.grid(row=2, column=1, sticky='w', pady=(10, 0))

        tz_lbl = ttk.Label(frm, text='时区：')
        tz_lbl.grid(row=2, column=2, sticky='w', pady=(10, 0))
        self.tz_var = tk.StringVar(value='Local')
        tz_combo = ttk.Combobox(frm, textvariable=self.tz_var, values=['Local', 'UTC'], width=8, state='readonly')
        tz_combo.grid(row=2, column=3, sticky='w', pady=(10, 0))

        # Output scale for time->timestamp
        outscale_lbl = ttk.Label(frm, text='输出单位：')
        outscale_lbl.grid(row=3, column=0, sticky='w', pady=(10, 0))
        self.outscale_var = tk.StringVar(value='seconds')
        out_combo = ttk.Combobox(frm, textvariable=self.outscale_var, values=['seconds', 'milliseconds', 'microseconds', 'nanoseconds'], width=14, state='readonly')
        out_combo.grid(row=3, column=1, sticky='w', pady=(10, 0))

        # Buttons
        btn_convert = ttk.Button(frm, text='转换', command=self.convert)
        btn_convert.grid(row=3, column=3, sticky='e', pady=(10, 0))

        btn_clear = ttk.Button(frm, text='清空', command=self._clear)
        btn_clear.grid(row=3, column=4, sticky='w', pady=(10, 0))

        # Result
        res_lbl = ttk.Label(frm, text='结果：')
        res_lbl.grid(row=4, column=0, sticky='nw', pady=(12, 0))
        self.result_text = tk.Text(frm, height=6, width=70, state='normal')
        self.result_text.grid(row=4, column=1, columnspan=4, pady=(12, 0))

        btn_copy = ttk.Button(frm, text='复制结果', command=self._copy_result)
        btn_copy.grid(row=5, column=4, sticky='e', pady=(8, 0))

        # Status
        self.status_var = tk.StringVar(value='就绪')
        status_lbl = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w')
        status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

        # initial state
        self._on_mode_change()

    def _on_mode_change(self):
        mode = self.mode.get()
        if mode == 'ts2time':
            # hide format/outscale? We'll keep them but disable
            self.format_entry.config(state='disabled')
            self.format_var.set('%Y-%m-%d %H:%M:%S')
            self.format_entry.configure(state='disabled')
        else:
            self.format_entry.configure(state='normal')

    def _clear(self):
        self.input_text.delete('1.0', tk.END)
        self.result_text.delete('1.0', tk.END)
        self.status_var.set('已清空')

    def _copy_result(self):
        txt = self.result_text.get('1.0', tk.END).strip()
        if not txt:
            messagebox.showinfo('提示', '没有结果可以复制')
            return
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.status_var.set('已复制到剪贴板')

    def convert(self):
        mode = self.mode.get()
        raw = self.input_text.get('1.0', tk.END).strip()
        if not raw:
            messagebox.showwarning('输入为空', '请在输入框中输入要转换的内容')
            return
        try:
            if mode == 'ts2time':
                self.status_var.set('正在解析时间戳...')
                dt = timestamp_to_dt(raw, tz=self.tz_var.get())
                fmt = self.format_var.get() or '%Y-%m-%d %H:%M:%S'
                # show several formats
                lines = []
                lines.append(f'检测到时区: {self.tz_var.get()}')
                lines.append('')
                try:
                    lines.append('格式化输出: ' + dt.strftime(fmt))
                except Exception as e:
                    lines.append('格式化输出失败: ' + str(e))
                # ISO / RFC3339
                try:
                    if dt.tzinfo is None:
                        # make ISO with local offset unknown
                        lines.append('ISO 8601: ' + dt.isoformat(' '))
                    else:
                        lines.append('ISO 8601: ' + dt.astimezone(timezone.utc).isoformat())
                except Exception:
                    lines.append('ISO 8601: ' + dt.isoformat())

                # Also include canonical timestamps in seconds/ms/us/ns
                sec = int(dt.timestamp())
                lines.append('')
                lines.append(f'seconds (10位): {sec}')
                lines.append(f'milliseconds (13位): {int(dt.timestamp() * 1000)}')
                lines.append(f'microseconds (16位): {int(dt.timestamp() * 1_000_000)}')
                lines.append(f'nanoseconds (19位): {int(dt.timestamp() * 1_000_000_000)}')

                self.result_text.config(state='normal')
                self.result_text.delete('1.0', tk.END)
                self.result_text.insert(tk.END, '\n'.join(lines))
                self.result_text.config(state='disabled')
                self.status_var.set('转换完成')

            else:  # time2ts
                self.status_var.set('正在解析时间字符串...')
                fmt = self.format_var.get() or '%Y-%m-%d %H:%M:%S'
                # try parse possibly multiple lines; use first non-empty
                line = None
                for l in raw.splitlines():
                    if l.strip():
                        line = l.strip()
                        break
                if line is None:
                    raise ValueError('没有可解析的时间字符串')

                # parse
                try:
                    dt = datetime.strptime(line, fmt)
                except Exception as e:
                    # helpful fallback: try common ISO formats
                    try:
                        dt = datetime.fromisoformat(line)
                    except Exception:
                        raise

                ts = dt_to_timestamp(dt, out_scale=self.outscale_var.get(), tz=self.tz_var.get())
                lines = []
                lines.append(f'解析时间: {dt} (假定时区: {self.tz_var.get()})')
                lines.append(f'输出 ({self.outscale_var.get()}): {ts}')

                self.result_text.config(state='normal')
                self.result_text.delete('1.0', tk.END)
                self.result_text.insert(tk.END, '\n'.join(lines))
                self.result_text.config(state='disabled')
                self.status_var.set('转换完成')

        except Exception as e:
            self.status_var.set('错误')
            messagebox.showerror('转换失败', str(e))


if __name__ == '__main__':
    app = TimestampConverter()
    app.mainloop()

