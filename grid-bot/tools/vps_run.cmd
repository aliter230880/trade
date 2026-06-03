@echo off
REM Утилита для запуска команды на VPS через plink
REM Использование: vps_run.cmd "команда в кавычках"
"C:\Program Files\PuTTY\plink.exe" -ssh -batch -pw ShAVSu2ZM57U7jFB -hostkey SHA256:kTPrb01XLPu73Wwm45TIweNoMja2WroQnMRDblRi4e8 root@168.222.143.103 %*
