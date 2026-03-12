@echo off
setlocal

cd /d C:\Users\slime\Desktop\picksale-ingestor

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name picksale_ingestor ^
  --add-data ".env;." ^
  main.py

endlocal
