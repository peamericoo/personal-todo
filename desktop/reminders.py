#!/usr/bin/env python3
"""Notificações de lembretes para a sessão gráfica Linux."""
import json, os, sqlite3, subprocess, sys, time, urllib.request
from settings import connection, safe_url
from datetime import datetime, timezone
from pathlib import Path

def token():
    return connection()[1]

def fetch(key):
    cursor=None
    while True:
        args={'tipo':'atividade','concluida':False,'limite':100}
        if cursor is not None: args['cursor']=cursor
        body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'listar_itens','arguments':args}}).encode()
        url,_=connection()
        if not safe_url(url): raise RuntimeError('Servidor não configurado ou inseguro')
        req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Authorization':'Bearer '+key})
        with urllib.request.urlopen(req,timeout=20) as response: data=json.load(response)
        result=data['result']
        if result.get('isError'): raise RuntimeError('Consulta de lembretes falhou')
        page=json.loads(result['content'][0]['text']); yield from page['itens']; cursor=page.get('proximo_cursor')
        if cursor is None:break

def notify(title):
    if sys.platform=='darwin':
        subprocess.run(['osascript','-e','on run argv\n display notification (item 1 of argv) with title "Personal To-Do" subtitle "Lembrete"\nend run',title],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    elif sys.platform=='win32':
        # Desktop toasts require an installed shortcut with an AppUserModelID.
        # Do not mark a reminder delivered until the Windows installer supplies it.
        raise RuntimeError('Notificações Windows ainda não configuradas')
    else: subprocess.run(['notify-send','--app-name=Personal To-Do','Lembrete',title],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def check(db,key,now=None,send=None):
    now=now or datetime.now(timezone.utc)
    send=send or notify
    for item in fetch(key):
        due=item.get('lembrete_utc')
        if not due: continue
        try: when=datetime.fromisoformat(due.replace('Z','+00:00'))
        except ValueError: continue
        if when.tzinfo is None or when>now: continue
        if db.execute('SELECT 1 FROM delivered WHERE item=? AND reminder=?',(item['id'],due)).fetchone():continue
        send(item['titulo']); db.execute('INSERT OR IGNORE INTO delivered(item,reminder) VALUES(?,?)',(item['id'],due)); db.commit()

def main():
    state=Path(os.getenv('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'personal-todo';state.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=(state/'reminders.lock').open('w')
    try:
        if os.name=='nt':
            import msvcrt
            lock.write('0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (BlockingIOError,OSError):return
    db=sqlite3.connect(state/'reminders.sqlite3'); db.execute('CREATE TABLE IF NOT EXISTS delivered(item INTEGER NOT NULL, reminder TEXT NOT NULL, PRIMARY KEY(item,reminder))'); db.commit(); os.chmod(state/'reminders.sqlite3',0o600)
    while True:
        try:
            key=token()
            if key:check(db,key)
        except Exception as exc: print('Lembretes indisponíveis:',type(exc).__name__,file=sys.stderr,flush=True)
        time.sleep(60)
if __name__=='__main__':main()
