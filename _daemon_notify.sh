#!/bin/bash
cd /root/quant-system
while true; do
    python3 -c "
import subprocess, os, glob, json

QUEUE_DIR = '/root/quant-system/.notify_queue'
SENT_DIR = '/root/quant-system/.notify_sent'
os.makedirs(SENT_DIR, exist_ok=True)

files = sorted(glob.glob(os.path.join(QUEUE_DIR, '*.json')), 
               key=lambda x: (0 if os.path.basename(x).startswith('high_') else 1, x))
               
for filepath in files:
    try:
        with open(filepath) as f:
            data = json.load(f)
        msg = data.get('message','')
        target = data.get('target','o9cq80yJxHbRLO8tbYzQlJu3IoJI@im.wechat')
        account = data.get('accountId','46dec126a996-im-bot')
        
        r = subprocess.run(['/root/.local/share/pnpm/openclaw','message','send','--channel','openclaw-weixin',
                            '--target',target,'-m',msg],
                           capture_output=True,text=True,timeout=20)
        if r.returncode == 0:
            print('SENT:', msg[:50])
            os.rename(filepath, os.path.join(SENT_DIR, os.path.basename(filepath)))
        else:
            print('FAIL:', r.stderr[:100])
    except Exception as e:
        print('ERR:', e)
"
    sleep 15
done
