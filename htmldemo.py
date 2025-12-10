#!/usr/bin/env python3
"""漂亮的扁平化按钮（tkinter + Canvas）

保存为 flat_button.py 后运行： python3 flat_button.py

修正说明：
- 修复了变量名覆盖 tkinter 内部属性 `_w` 导致的 `_tkinter.TclError: invalid command name "180"` 错误。
  现在使用 self._width / self._height / self._radius 代替之前的 self._w / self._h / self._r。

特点：
- 扁平化、圆角设计
- 悬停 / 按下 视觉反馈
- 可自定义颜色、圆角、阴影、字体
- 支持禁用态
"""

import tkinter as tk
from tkinter import font as tkfont


class FlatButton(tk.Canvas):
    """基于 Canvas 的扁平化按钮

    使用示例：
        btn = FlatButton(root, text="Click me", command=lambda: print('clicked'))
        btn.pack(padx=20, pady=20)
    """

    def __init__(self, master, text='', command=None,
                 width=140, height=44, radius=12,
                 bg='#F3F7FF', fg='#0B3D91', hover_bg='#E6EEFF', active_bg='#D3E4FF',
                 shadow=True, shadow_color='#DCE9FF', font=None, disabled=False, **kwargs):
        super().__init__(master, width=width, height=height, highlightthickness=0, bg=master['bg'], **kwargs)
        # 使用不与 tkinter 内部属性冲突的实例变量名
        self._width = width
        self._height = height
        self._radius = max(0, min(radius, height//2))
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._active_bg = active_bg
        self._shadow = shadow
        self._shadow_color = shadow_color
        self._font = font or tkfont.Font(family='Helvetica', size=11, weight='bold')
        self._disabled = disabled

        self._state = 'normal'  # normal / hover / active / disabled

        # canvas items
        self._shadow_id = None
        self._rect_id = None
        self._text_id = None

        self._draw()
        self._bind_events()

    def _round_rect_coords(self, x1, y1, x2, y2, r):
        return (x1+r, y1, x2-r, y2, x1, y1+r, x1, y2-r, x2, y1+r, x2, y2-r)

    def _draw(self):
        self.delete('all')
        pad = 2
        if self._shadow:
            # shadow is slightly offset and softer (simulated)
            self._shadow_id = self.create_round_rect(pad+2, pad+4, self._width-pad+2, self._height-pad+4, self._radius, fill=self._shadow_color, outline='')

        fill = self._bg if self._state in ('normal','disabled') else (self._hover_bg if self._state=='hover' else self._active_bg)
        if self._disabled:
            fill = '#EEEEEE'
            fg = '#A0A0A0'
        else:
            fg = self._fg

        self._rect_id = self.create_round_rect(pad, pad, self._width-pad, self._height-pad, self._radius, fill=fill, outline='')
        self._text_id = self.create_text(self._width//2, self._height//2, text=self._text, font=self._font, fill=fg)

    def create_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        # draw a rounded rectangle by arcs + rectangles
        if r <= 0:
            return self.create_rectangle(x1, y1, x2, y2, **kwargs)
        # corners (arcs). 使用 pieslice 填充圆角
        tl = self.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, style='pieslice', **kwargs)
        tr = self.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, style='pieslice', **kwargs)
        bl = self.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, style='pieslice', **kwargs)
        br = self.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, style='pieslice', **kwargs)
        # center rectangles to fill
        rect1 = self.create_rectangle(x1+r, y1, x2-r, y2, **kwargs)
        rect2 = self.create_rectangle(x1, y1+r, x2, y2-r, **kwargs)
        # 返回一个代表主矩形的 id
        return rect2

    def _bind_events(self):
        # 解绑旧的绑定（防止重复绑定）
        try:
            if self._rect_id:
                self.tag_unbind(self._rect_id, '<Enter>')
        except Exception:
            pass

        # 绑定事件到当前绘制的项目
        if self._rect_id:
            self.tag_bind(self._rect_id, '<Enter>', lambda e: self._on_enter())
            self.tag_bind(self._rect_id, '<Leave>', lambda e: self._on_leave())
            self.tag_bind(self._rect_id, '<Button-1>', lambda e: self._on_press())
            self.tag_bind(self._rect_id, '<ButtonRelease-1>', lambda e: self._on_release())
        if self._text_id:
            self.tag_bind(self._text_id, '<Enter>', lambda e: self._on_enter())
            self.tag_bind(self._text_id, '<Leave>', lambda e: self._on_leave())
            self.tag_bind(self._text_id, '<Button-1>', lambda e: self._on_press())
            self.tag_bind(self._text_id, '<ButtonRelease-1>', lambda e: self._on_release())
        # 也绑定到 canvas 本身以捕捉阴影等区域
        self.bind('<Enter>', lambda e: self._on_enter())
        self.bind('<Leave>', lambda e: self._on_leave())

    def _on_enter(self):
        if self._disabled:
            return
        self._state = 'hover'
        self._animate_hover(True)

    def _on_leave(self):
        if self._disabled:
            return
        self._state = 'normal'
        self._animate_hover(False)

    def _on_press(self):
        if self._disabled:
            return
        self._state = 'active'
        # visual press: move down a bit
        self.move('all', 0, 1)
        self._update_fill()

    def _on_release(self):
        if self._disabled:
            return
        # move back
        self.move('all', 0, -1)
        self._state = 'hover'
        self._update_fill()
        if callable(self._command):
            try:
                self._command()
            except Exception as e:
                print('button command error:', e)

    def _update_fill(self):
        fill = self._bg if self._state in ('normal','disabled') else (self._hover_bg if self._state=='hover' else self._active_bg)
        if self._disabled:
            fill = '#EEEEEE'
            fg = '#A0A0A0'
        else:
            fg = self._fg
        # itemconfig works因为我们使用了矩形和文字
        if self._rect_id:
            self.itemconfig(self._rect_id, fill=fill)
        if self._text_id:
            self.itemconfig(self._text_id, fill=fg)

    def _animate_hover(self, enter):
        # 一个简单的即时视觉反馈（没有复杂插值）
        self._update_fill()

    # public API
    def config(self, **kwargs):
        # allow updating some properties
        for k, v in kwargs.items():
            if k == 'text':
                self._text = v
            elif k == 'command':
                self._command = v
            elif k == 'bg':
                self._bg = v
            elif k == 'fg':
                self._fg = v
            elif k == 'hover_bg':
                self._hover_bg = v
            elif k == 'active_bg':
                self._active_bg = v
            elif k == 'disabled':
                self._disabled = bool(v)
        self._draw()
        self._bind_events()


if __name__ == '__main__':
    root = tk.Tk()
    root.title('扁平化按钮示例')
    root.geometry('520x260')
    root.configure(bg='#F5F8FF')

    frame = tk.Frame(root, bg=root['bg'])
    frame.pack(expand=True)

    def on_click():
        print('按钮被点击！')

    b1 = FlatButton(frame, text='主要操作', command=on_click, width=180, height=50,
                    bg='#2563EB', fg='white', hover_bg='#1E40AF', active_bg='#17307A',
                    shadow=True, shadow_color='#CFE0FF')
    b1.grid(row=0, column=0, padx=20, pady=20)

    b2 = FlatButton(frame, text='次要操作', command=lambda: print('次要'), width=140, height=44,
                    bg='#E6F0FF', fg='#2563EB', hover_bg='#D7E8FF', active_bg='#C6DDFF',
                    shadow=False)
    b2.grid(row=0, column=1, padx=10, pady=20)

    b3 = FlatButton(frame, text='禁用', command=None, width=140, height=44, disabled=True)
    b3.grid(row=1, column=0, padx=20, pady=10)

    # 展示不同尺寸
    b4 = FlatButton(frame, text='小按钮', width=100, height=34, bg='#10B981', fg='white', shadow=False)
    b4.grid(row=1, column=1, padx=10, pady=10)

    root.mainloop()

