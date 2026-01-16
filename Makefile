all:
	sudo apt install -y python3-tk
	. /opt/venv/bin/activate && pyinstaller --onefile jsonxml.py
	. /opt/venv/bin/activate && pyinstaller --onefile jwt.py
	. /opt/venv/bin/activate && pyinstaller --onefile script-ui.py
	. /opt/venv/bin/activate && pyinstaller --onefile tostruct.py
	. /opt/venv/bin/activate && pyinstaller --onefile kdev.py
	. /opt/venv/bin/activate && pyinstaller --onefile convert-time.py
	. /opt/venv/bin/activate && pyinstaller --onefile convert-excel.py
	. /opt/venv/bin/activate && pyinstaller --onefile json_counter.py
	. /opt/venv/bin/activate && pyinstaller --onefile csv_not_existed.py
	. /opt/venv/bin/activate && pyinstaller --onefile json_total.py
	. /opt/venv/bin/activate && pyinstaller --onefile --hidden-import=flat_dark_theme dark.py
	. /opt/venv/bin/activate && pyinstaller --onefile member.py
