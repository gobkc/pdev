#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.py.debbuilder")

    def do_activate(self):
        css = b"""
        headerbar, *{
            background-color: black;
            background-image: none;
            color: #cccccc;
            border: 0px;
        }
        headerbar button{
            border: 0px!important;
        }
        entry{
            background-color: #000000;
            color: #cccccc;
            border-bottom: 1px solid green;
            border-top: 0px;
            border-left: 0px;
            border-right: 0px;
            border-radius: 0px;
            outline: none;
        }
        textview{
            background-color: #000000;
            color: #cccccc;
            border: 1px solid green;
            border-radius: 0px;
            outline: none;
            padding:15px;
        }
        entry selection,textview selection{
            background-color: #3c78d0;
            color: #ffffff;
        }
        button{
            background-color: black;
            border-radius: 5px;
            border: 1px solid #333333;
        }
        button:hover {
            border: 1px solid #666666;
        }
        scrollbar {
            background-color: #000000;
        }
        .file-list {
            font-size: 10px;
            color: #888888;
        }
        .gen_deb{
            background-color: rgba(255,0,0,0.55);
            padding-top:15px;
            padding-bottom:15px;
            border: none;
        }
        .gen_deb:hover{
            background-color: rgba(255,0,0,0.60);
            border: none;
        }
        .gen_deb label{
            background-color: transparent;
            color: #cccccc;
        }
        """

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win = MainWindow(self)
        win.present()


class DebBuilder:
    def __init__(self, log_func):
        self.log = log_func

    def build(self, config):
        try:
            pkg = config["package"]
            version = config["version"]
            arch = config["architecture"]
            depends = config["depends"]
            maintainer = config["maintainer"]
            desc = config["description"]
            categories = config["categories"]
            wm_class = config["wm_class"]
            install_path = config["install_path"]
            output_dir = config["output_dir"]

            exec_files = config["exec_files"]
            icon_files = config["icon_files"]

            if not pkg or not version:
                raise Exception("Package 和 Version 不能为空")

            temp_dir = tempfile.mkdtemp(prefix="debbuild_")
            root = os.path.join(temp_dir, f"{pkg}")
            debian_dir = os.path.join(root, "DEBIAN")

            # 目标目录
            exec_dir = os.path.join(root, install_path.strip("/"))
            icon_dir = os.path.join(root, "usr/share/icons/hicolor/48x48/apps")
            desktop_dir = os.path.join(root, "usr/share/applications")
            bin_dir = os.path.join(root, "usr/bin")

            os.makedirs(debian_dir, exist_ok=True)
            os.makedirs(exec_dir, exist_ok=True)
            os.makedirs(icon_dir, exist_ok=True)
            os.makedirs(desktop_dir, exist_ok=True)
            os.makedirs(bin_dir, exist_ok=True)

            self.log(f"📁 构建目录: {root}")

            # 复制可执行文件并设置执行权限
            exec_paths = []
            for f in exec_files:
                src = f.get_path()
                dst = os.path.join(exec_dir, os.path.basename(src))
                shutil.copy(src, dst)
                os.chmod(dst, 0o755)  # 添加执行权限
                exec_paths.append(dst)
                self.log(f"📄 复制可执行文件: {src} -> 权限已设置")

            # 复制图标（如果有）
            icon_paths = []
            for f in icon_files:
                src = f.get_path()
                dst = os.path.join(icon_dir, os.path.basename(src))
                shutil.copy(src, dst)
                icon_paths.append(dst)
                self.log(f"📄 复制图标: {src}")

            # 获取第一个图标的完整安装路径（用于 .desktop）
            first_icon = None
            if icon_paths:
                # 使用图标名（不带路径和扩展名）
                icon_filename = os.path.basename(icon_paths[0])
                first_icon = os.path.splitext(icon_filename)[0]
                self.log(f"🔧 图标名称: {first_icon}")

            # 为每个可执行文件生成启动器脚本和 .desktop
            for i, f in enumerate(exec_files):
                exec_filename = os.path.basename(f.get_path())
                # 去掉扩展名
                base_name = os.path.splitext(exec_filename)[0]

                # 生成规范的桌面文件名和窗口类
                if wm_class and wm_class.strip():
                    # 如果用户指定了窗口类，使用它
                    if len(exec_files) > 1:
                        app_wm_class = f"{wm_class}.{base_name}".lower()
                        desktop_filename = f"{app_wm_class}.desktop"
                    else:
                        app_wm_class = wm_class.lower()
                        desktop_filename = f"{app_wm_class}.desktop"
                else:
                    # 默认使用包名和可执行文件名
                    app_wm_class = f"{pkg}.{base_name}".lower()
                    desktop_filename = f"{app_wm_class}.desktop"

                # Name: 首字母大写
                desktop_name = base_name.capitalize()
                # Exec: bash -c "完整路径"
                full_exec_path = os.path.join(install_path, exec_filename)
                exec_line = f'bash -c "{full_exec_path}"'
                # Comment: 路径 + 名称
                comment = f"{install_path}/{exec_filename}"

                # 创建启动器脚本（可选，用于更好的集成）
                launcher_path = os.path.join(bin_dir, app_wm_class)
                launcher_content = f"""#!/bin/sh
exec {full_exec_path} "$@"
"""
                with open(launcher_path, "w") as lf:
                    lf.write(launcher_content)
                os.chmod(launcher_path, 0o755)
                self.log(f"📄 生成启动器脚本: {app_wm_class}")

                # 生成 .desktop 内容
                desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={desktop_name}
Exec={exec_line}
"""
                if first_icon:
                    desktop_content += f"Icon={first_icon}\n"
                desktop_content += f"""Comment={comment}
Categories={categories}
Terminal=false
StartupNotify=true
StartupWMClass={app_wm_class}
"""
                # 写入 .desktop 文件
                desktop_path = os.path.join(desktop_dir, desktop_filename)
                with open(desktop_path, "w") as df:
                    df.write(desktop_content)
                self.log(
                    f"📄 生成桌面文件: {desktop_filename} (WM_CLASS: {app_wm_class})"
                )

            # 生成 postinst 脚本（更新图标缓存和桌面数据库）
            postinst_content = """#!/bin/sh
set -e

# 更新图标缓存
if [ -x /usr/bin/update-icon-caches ]; then
    /usr/bin/update-icon-caches /usr/share/icons/hicolor/
fi

# 更新桌面数据库
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database
fi

# 验证桌面文件
for desktop in /usr/share/applications/*.desktop; do
    if [ -f "$desktop" ] && [ -x /usr/bin/desktop-file-validate ]; then
        desktop-file-validate "$desktop" 2>/dev/null || true
    fi
done

exit 0
"""

            postinst_path = os.path.join(debian_dir, "postinst")
            with open(postinst_path, "w") as f:
                f.write(postinst_content)
            os.chmod(postinst_path, 0o755)
            self.log("📝 postinst 脚本已生成")

            # control 文件
            control = f"""Package: {pkg}
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: {maintainer}
Depends: {depends}
Description: {desc}
"""

            control_path = os.path.join(debian_dir, "control")
            with open(control_path, "w") as f:
                f.write(control)

            os.chmod(control_path, 0o644)

            self.log("📝 control 文件已生成")

            # 构建 deb
            output_deb = f"{pkg}_{version}.deb"
            output_path = os.path.join(output_dir, output_deb)
            cmd = ["dpkg-deb", "--build", root, output_path]

            self.log(f"🚀 执行: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(result.stderr)

            self.log(f"✅ 构建成功: {output_path}")

        except Exception as e:
            self.log(f"❌ 错误: {str(e)}")


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_title_buttons(True)
        headerbar.set_title_widget(Gtk.Label(label="Deb Builder Pro"))
        self.set_titlebar(headerbar)

        self.set_title("Deb Builder Pro")
        self.set_default_size(900, 600)

        self.builder = DebBuilder(self.log)

        # 存储两种文件列表
        self.exec_files = []
        self.icon_files = []

        # 主垂直容器
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        self.set_child(vbox)

        # 左右水平容器
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_hexpand(True)
        vbox.append(hbox)

        # 左侧：输入数据
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_box.set_hexpand(True)
        hbox.append(left_box)

        # 右侧：选择/生成
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_hexpand(True)
        hbox.append(right_box)

        # === 左侧：表单 ===
        self.pkg = self.form_row("Package:", left_box, "myapp")
        self.ver = self.form_row("Version:", left_box, "1.0")
        self.arch = self.form_combo("Architecture:", ["amd64", "all"], left_box, "all")
        self.dep = self.form_row("Depends (comma):", left_box, "")
        self.maint = self.form_row(
            "Maintainer:", left_box, "Unknown <unknown@example.com>"
        )
        self.categories = self.form_row("Categories:", left_box, "Development;")
        self.wm_class = self.form_row("窗口类 (WM_CLASS):", left_box, "myapp")
        self.path = self.form_row("Install Path:", left_box, "/usr/local/bin")

        # Description
        desc_label = self.label("Description:")
        left_box.append(desc_label)
        self.desc = Gtk.TextView()
        self.desc.set_vexpand(True)
        self.desc.set_size_request(-1, 100)
        left_box.append(self.desc)
        buffer = self.desc.get_buffer()
        buffer.set_text("A brief description")

        # === 右侧：文件选择区域 ===
        # 可执行文件
        exec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        exec_label = self.label("可执行文件:")
        exec_btn = Gtk.Button(label="选择可执行文件（多选）")
        exec_btn.connect("clicked", self.select_exec_files)
        self.exec_count_label = Gtk.Label(label="未选择")
        self.exec_count_label.set_xalign(0)
        self.exec_list_label = Gtk.Label(label="")
        self.exec_list_label.set_xalign(0)
        self.exec_list_label.get_style_context().add_class("file-list")
        exec_box.append(exec_label)
        exec_box.append(exec_btn)
        exec_box.append(self.exec_count_label)
        exec_box.append(self.exec_list_label)
        right_box.append(exec_box)

        # 图标
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        icon_label = self.label("图标文件:")
        icon_btn = Gtk.Button(label="选择图标文件（多选）")
        icon_btn.connect("clicked", self.select_icon_files)
        self.icon_count_label = Gtk.Label(label="未选择")
        self.icon_count_label.set_xalign(0)
        self.icon_list_label = Gtk.Label(label="")
        self.icon_list_label.set_xalign(0)
        self.icon_list_label.get_style_context().add_class("file-list")
        icon_box.append(icon_label)
        icon_box.append(icon_btn)
        icon_box.append(self.icon_count_label)
        icon_box.append(self.icon_list_label)
        right_box.append(icon_box)

        # 输出目录选择
        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        output_label = self.label("DEB 输出目录:")
        output_btn = Gtk.Button(label="选择输出目录")
        output_btn.connect("clicked", self.select_output_dir)
        self.output_dir_label = Gtk.Label(label="当前目录")
        self.output_dir_label.set_xalign(0)
        output_box.append(output_label)
        output_box.append(output_btn)
        output_box.append(self.output_dir_label)
        right_box.append(output_box)

        # 构建按钮（占满右侧宽度）
        build_btn = Gtk.Button(label="生成 DEB")
        build_btn.set_halign(Gtk.Align.FILL)
        build_btn.connect("clicked", self.build)
        build_btn.get_style_context().add_class("gen_deb")
        right_box.append(build_btn)

        # 添加弹性空间，将按钮推到上方（可选）
        # right_box.append(Gtk.Label())  # 不添加，保持紧凑

        # === 底部：日志（固定高度）===
        log_label = self.label("日志:")
        vbox.append(log_label)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_size_request(-1, 150)
        self.log_view = Gtk.TextView(editable=False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_scroll.set_child(self.log_view)
        vbox.append(log_scroll)

        # 保存输出目录的路径
        self.output_dir = os.getcwd()

    def label(self, text):
        l = Gtk.Label(label=text)
        l.set_xalign(0)
        return l

    def form_row(self, label_text, parent, default=""):
        """创建水平表单行：左边label，右边entry"""
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_size_request(120, -1)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_hexpand(True)
        row_box.append(label)
        row_box.append(entry)
        parent.append(row_box)
        return entry

    def form_combo(self, label_text, items, parent, default=None):
        """创建水平表单行：左边label，右边combo"""
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_size_request(120, -1)
        combo = Gtk.ComboBoxText()
        combo.set_hexpand(True)
        for i in items:
            combo.append_text(i)
        if default and default in items:
            combo.set_active(items.index(default))
        else:
            combo.set_active(0)
        row_box.append(label)
        row_box.append(combo)
        parent.append(row_box)
        return combo

    def log(self, text):
        buffer = self.log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, text + "\n")
        mark = buffer.create_mark(None, buffer.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        buffer.delete_mark(mark)

    def select_exec_files(self, btn):
        self._select_files("exec")

    def select_icon_files(self, btn):
        self._select_files("icon")

    def select_output_dir(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="选择输出目录",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK
        )
        dialog.connect("response", self.on_output_dir)
        dialog.show()

    def on_output_dir(self, dialog, resp):
        if resp == Gtk.ResponseType.OK:
            folder = dialog.get_file()
            if folder:
                self.output_dir = folder.get_path()
                self.output_dir_label.set_text(self.output_dir)
                self.log(f"输出目录设置为: {self.output_dir}")
        dialog.destroy()

    def _select_files(self, file_type):
        dialog = Gtk.FileChooserDialog(
            title="选择文件",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK
        )
        dialog.set_select_multiple(True)
        dialog.file_type = file_type
        dialog.connect("response", self.on_files)
        dialog.show()

    def on_files(self, dialog, resp):
        if resp == Gtk.ResponseType.OK:
            files = dialog.get_files()
            file_type = dialog.file_type
            file_paths = [f.get_path() for f in files]

            if file_type == "exec":
                self.exec_files = files
                self.exec_count_label.set_text(f"已选择 {len(files)} 个文件")
                # 显示具体文件列表
                file_list_text = "\n".join(
                    [f"  • {os.path.basename(p)}" for p in file_paths]
                )
                self.exec_list_label.set_text(
                    file_list_text if file_list_text else "未选择"
                )
                self.log(f"已选择 {len(files)} 个可执行文件:")
                for p in file_paths:
                    self.log(f"  - {p}")
            elif file_type == "icon":
                self.icon_files = files
                self.icon_count_label.set_text(f"已选择 {len(files)} 个文件")
                # 显示具体文件列表
                file_list_text = "\n".join(
                    [f"  • {os.path.basename(p)}" for p in file_paths]
                )
                self.icon_list_label.set_text(
                    file_list_text if file_list_text else "未选择"
                )
                self.log(f"已选择 {len(files)} 个图标文件:")
                for p in file_paths:
                    self.log(f"  - {p}")

        dialog.destroy()

    def build(self, btn):
        buffer = self.desc.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

        config = {
            "package": self.pkg.get_text(),
            "version": self.ver.get_text(),
            "architecture": self.arch.get_active_text(),
            "depends": self.dep.get_text(),
            "maintainer": self.maint.get_text(),
            "categories": self.categories.get_text(),
            "wm_class": self.wm_class.get_text(),
            "description": text.strip(),
            "install_path": self.path.get_text() or "/usr/local/bin",
            "output_dir": self.output_dir,
            "exec_files": self.exec_files,
            "icon_files": self.icon_files,
        }

        self.builder.build(config)


app = App()
app.run()
