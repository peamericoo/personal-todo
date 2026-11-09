import sys
sys.path.insert(0, "desktop")
import importlib.util,json,os,sqlite3,subprocess,tempfile,time,urllib.request
from datetime import datetime, timezone
with tempfile.TemporaryDirectory() as d:
 path=d+'/db'; db=sqlite3.connect(path)
 db.execute("CREATE TABLE items(id INTEGER PRIMARY KEY,tipo TEXT NOT NULL,titulo TEXT NOT NULL,descricao TEXT,prazo TEXT,concluida INTEGER NOT NULL DEFAULT 0,pai_id INTEGER REFERENCES items(id) ON DELETE CASCADE,criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
 db.execute("INSERT INTO items(tipo,titulo) VALUES('atividade','Existente')");db.commit();db.close()
 token='test-'+('x'*48); env=dict(os.environ,PORT='19885',MCP_TOKEN=token,DATABASE_PATH=path)
 p=subprocess.Popen(['target/release/personal-todo'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 try:
  for _ in range(100):
   try:urllib.request.urlopen('http://127.0.0.1:19885/health',timeout=1);break
   except Exception:time.sleep(.05)
  def call(name,args,err=False):
   data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}).encode()
   req=urllib.request.Request('http://127.0.0.1:19885/mcp',data=data,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
   result=json.load(urllib.request.urlopen(req))['result'];assert result.get('isError',False)==err,result
   return result['content'][0]['text'] if err else json.loads(result['content'][0]['text'])
  assert call('obter_item',{'id':1})['item']['titulo']=='Existente'
  assert call('obter_item',{'id':1})['item']['lembrete_utc'] is None
  item=call('atualizar_item',{'id':1,'lembrete_utc':'2026-11-09T13:00:00-04:00'})
  assert item['lembrete_utc']=='2026-11-09T17:00:00Z' and item['tags']==[]
  item=call('atualizar_item',{'id':1,'tags':['Aguardando','Urgente','aguardando']}); assert item['tags']==['Aguardando','Urgente']
  assert call('listar_itens',{})['itens'][0]['tags']==['Aguardando','Urgente']
  call('atualizar_item',{'id':1,'tags':['x'*33]},True)
  assert call('atualizar_item',{'id':1,'titulo':'Existente'})['tags']==['Aguardando','Urgente']
  assert call('listar_itens',{})['itens'][0]['lembrete_utc']=='2026-11-09T17:00:00Z'
  call('atualizar_item',{'id':1,'lembrete_utc':'2026-11-09 13:00'},True)
  group=call('criar_item',{'tipo':'grupo','titulo':'grupo'})
  call('atualizar_item',{'id':group['id'],'lembrete_utc':'2026-11-09T17:00:00Z'},True);call('atualizar_item',{'id':group['id'],'tags':['x']},True)
  spec=importlib.util.spec_from_file_location('reminders','desktop/reminders.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  m.fetch=lambda key:[item]; notifications=[]; store=sqlite3.connect(':memory:');store.execute('CREATE TABLE delivered(item INTEGER, reminder TEXT, PRIMARY KEY(item,reminder))')
  m.check(store,token,datetime(2026,11,9,16,59,tzinfo=timezone.utc),notifications.append);assert notifications==[]
  m.check(store,token,datetime(2026,11,9,17,0,tzinfo=timezone.utc),notifications.append);m.check(store,token,datetime(2026,11,9,17,1,tzinfo=timezone.utc),notifications.append);assert notifications==['Existente']
  assert call('atualizar_item',{'id':1,'lembrete_utc':None})['lembrete_utc'] is None
  print('OK: migração de banco existente, fuso UTC, validação, remoção e notificação única')
 finally:p.terminate();p.wait()
