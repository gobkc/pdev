#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio
import json
import csv
import io

class JsonToCsvApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.jsontocsv')
    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self, title="JSON to CSV Converter")
        win.set_default_size(600, 400)

        # main vertical box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        win.set_child(box)

        # scrolled text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(self.textview)
        box.append(scrolled)

        # button
        self.button = Gtk.Button(label="Convert JSON to CSV")
        self.button.connect('clicked', self.on_convert_clicked)
        box.append(self.button)

        win.present()

    def on_convert_clicked(self, button):
        buffer = self.textview.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False)
        if not text.strip():
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            self.show_error(f"Invalid JSON: {e}")
            return
        if not isinstance(data, list):
            self.show_error("JSON must be an array of objects.")
            return
        if len(data) == 0:
            self.show_error("JSON array is empty.")
            return
        if not all(isinstance(item, dict) for item in data):
            self.show_error("Array must contain only objects.")
            return

        # Extract headers from the first object
        first_obj = data[0]
        headers = list(first_obj.keys())

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for row in data:
            # Convert values to strings safely (handle non-string types)
            str_row = {}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    str_row[k] = json.dumps(v)  # serialize nested structures
                else:
                    str_row[k] = v
            writer.writerow(str_row)

        csv_text = output.getvalue()
        buffer.set_text(csv_text)

    def show_error(self, message):
        self.textview.get_buffer().set_text(f"Error: {message}")

if __name__ == '__main__':
    app = JsonToCsvApp()
    app.run(None)
