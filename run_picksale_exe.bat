@echo off
cd /d C:\Users\slime\Desktop\picksale-ingestor
if not exist logs mkdir logs
echo ============================ >> logs\logs.txt
echo [%date% %time%] PickSale EXE start >> logs\logs.txt
if not exist dist\picksale_ingestor.exe (
    echo [%date% %time%] Missing dist\picksale_ingestor.exe >> logs\logs.txt
    exit /b 1
)
dist\picksale_ingestor.exe >> logs\logs.txt 2>&1
