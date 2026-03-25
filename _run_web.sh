#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /root/quant-system/web
exec /usr/bin/python3 -u app.py >> /root/quant-system/logs/web.log 2>&1
