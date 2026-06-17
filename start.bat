@echo off
REM Starter Abahne Discovery — Flask-server + åpner nettleser
title Abahne Discovery
echo Starter Flask-server pa http://127.0.0.1:5000 ...
start "" http://127.0.0.1:5000
python web/app.py
