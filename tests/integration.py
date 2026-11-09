import concurrent.futures, json, os, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request
binary=sys.argv[1] if len(sys.argv)>1 else 'target/release/personal-todo'
token='test-token-'+'x'*48
with tempfile.TemporaryDirectory() as d:
 env=dict(os.environ,PORT='19879',MCP_TOKEN=token,DATABASE_PATH=d+'/db.sqlite')
 def start():
  p=subprocess.Popen([binary],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for _ in range(100):
   try:
    with urllib.request.urlopen('http://127.0.0.1:19879/health',timeout=1):return p
   except Exception:
    if p.poll() is not None: raise RuntimeError(p.stderr.read().decode())
    time.sleep(.05)
  raise RuntimeError('Servidor não iniciou')
 def req(message,auth=True,origin=None):
  headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
  if auth:headers['Authorization']='Bearer '+token
  if origin:headers['Origin']=origin
  request=urllib.request.Request('http://127.0.0.1:19879/mcp',json.dumps(message).encode(),headers)
  try:
   with urllib.request.urlopen(request,timeout=10) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,None
 def rpc(method,params={}):
  status,result=req({'jsonrpc':'2.0','id':1,'method':method,'params':params});assert status==200,(status,result);return result
 def call(name,args,fail=False):
  result=rpc('tools/call',{'name':name,'arguments':args})['result']
  assert result.get('isError',False)==fail,result
  return result['content'][0]['text'] if fail else json.loads(result['content'][0]['text'])
 p=start()
 try:
  msg={'jsonrpc':'2.0','id':1,'method':'tools/list'}
  assert req(msg,False)[0]==401 and req(msg,True,'https://evil.example')[0]==403
  assert rpc('initialize',{'protocolVersion':'2025-06-18'})['result']['protocolVersion']=='2025-06-18'
  listed=rpc('tools/list')['result']['tools']; assert len(listed)==5
  assert next(t for t in listed if t['name']=='listar_itens')['annotations']['readOnlyHint']
  group=call('criar_item',{'tipo':'grupo','titulo':'Grupo'})['id'];folder=call('criar_item',{'tipo':'pasta','titulo':'Pasta','pai_id':group})['id']
  task=call('criar_item',{'tipo':'atividade','titulo':'Atividade','descricao':'Descrição completa','prazo':'29/02/2028','pai_id':folder})['id']
  call('criar_item',{'tipo':'atividade','titulo':'Inválida','prazo':'31/02/2028'},True)
  call('atualizar_item',{'id':group,'pai_id':folder},True)
  assert call('atualizar_item',{'id':task,'concluida':True})['concluida'] is True
  assert call('obter_item',{'id':task})['item']['descricao']=='Descrição completa'
  for i in range(47):call('criar_item',{'tipo':'atividade','titulo':f'Fila {i:02}','pai_id':folder,'descricao':'Detalhes extras'})
  ids=[];cursor=0
  while True:
   page=call('listar_itens',{'pai_id':folder,'limite':7,'cursor':cursor})
   for item in page['itens']:
    assert 'descricao' not in item;ids.append(item['id'])
   cursor=page['proximo_cursor']
   if cursor is None:break
  assert len(ids)==48 and len(set(ids))==48
  assert call('listar_itens',{'pai_id':folder,'detalhes':True,'limite':1})['itens'][0]['descricao']=='Descrição completa'
  first=call('obter_item',{'id':folder,'limite':7});assert len(first['filhos'])==7 and first['proximo_cursor']
  assert call('listar_itens',{'busca':'Fila 13','pai_id':folder})['itens'][0]['titulo']=='Fila 13'
  def read(_):return call('listar_itens',{'pai_id':folder,'limite':7})['itens'][0]['id']
  with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:assert len(list(pool.map(read,range(100))))==100
  p.terminate();p.wait();p=start()
  assert call('obter_item',{'id':task})['item']['prazo']=='29/02/2028'
  call('excluir_item',{'id':group,'confirmar':False},True)
  assert call('excluir_item',{'id':group,'confirmar':True})['total_excluido_incluindo_descendentes']==50
  assert call('listar_itens',{})['itens']==[]
  print('OK: autenticação, ferramentas MCP, CRUD, paginação sem perdas, filtros, dados detalhados, datas, 100 leituras concorrentes, persistência após reinício e exclusão em cascata.')
 finally:p.terminate();p.wait()
