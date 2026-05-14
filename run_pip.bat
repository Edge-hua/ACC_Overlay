@echo off
C:\Users\hzq\.conda\envs\ACC\python.exe -m pip install PyQt6 > C:\Users\hzq\Desktop\overlay\pip_log.txt 2>&1
C:\Users\hzq\.conda\envs\ACC\python.exe -c "import PyQt6; print('OK:' + PyQt6.QtCore.PYQT_VERSION_STR)" >> C:\Users\hzq\Desktop\overlay\pip_log.txt 2>&1
