@echo off
REM Утилита pscp для копирования файлов на VPS
REM Использование: vps_scp.cmd source target
"C:\Program Files\PuTTY\pscp.exe" -batch -pw ShAVSu2ZM57U7jFB -hostkey SHA256:kTPrb01XLPu73Wwm45TIweNoMja2WroQnMRDblRi4e8 %*
