#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

def on_button_clicked(text_view):
    text = text_view.get_text()
    parts = text.strip().split('.')
    if len(parts) != 3:
        return
    payload = parts[1]
    import base64
    payload_bytes = base64.urlsafe_b64decode(payload + '==')
    import json
    try:
        parsed = json.loads(payload_bytes.decode('utf-8'))
        text_view.set_text(json.dumps(parsed, indent=2))
    except Exception:
        text_view.set_text('Error: Invalid JWT payload')

def main():
    window = Gtk.Window()
    window.set_default_size(500, 400)
    window.set_title('JWT Payload Parser')
    
    box = Gtk.Box.new(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    
    text_view = Gtk.TextView()
    
    button = Gtk.Button(label='Parse JWT Payload')
    
    button.connect('clicked', on_button_clicked, text_view)
    
    box.pack_start(text_view, False, True, 0)
    box.pack_start(button, False, True, 0)
    
    window.append(box)
    window.connect('destroy', Gtk.main_quit)
    window.present()
    Gtk.main()

if __name__ == '__main__':
    main()

