#!/bin/bash
cd ~/Downloads/resurgeifi-app-main
source venv/bin/activate
python3 main.py
#!/bin/bash
gunicorn main:app
