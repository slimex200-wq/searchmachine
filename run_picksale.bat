@echo off
cd /d C:\Users\slime\Desktop\picksale-ingestor
if not exist logs mkdir logs
echo ============================ >> logs\logs.txt
echo [%date% %time%] PickSale crawler start >> logs\logs.txt
echo [%date% %time%] Running preflight tests >> logs\logs.txt
python -m unittest discover -s tests >> logs\logs.txt 2>&1
if errorlevel 1 (
    echo [%date% %time%] Preflight tests failed. Aborting crawler run. >> logs\logs.txt
    exit /b 1
)
echo [%date% %time%] Preflight tests passed >> logs\logs.txt
python main.py >> logs\logs.txt 2>&1
