@echo off
cd /d "C:\Work\Mantella"
call MantellaEnv\Scripts\Activate.bat
cd /d "D:\Modding\MO2\mods\Mantella - Bring NPCs to Life with AI\SKSE\Plugins\MantellaSoftware"
python "C:\Work\Mantella\main.py"
pause
