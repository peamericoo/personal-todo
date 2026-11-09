import os,sqlite3,subprocess,tempfile,time,urllib.request,json,statistics,sys
binary=sys.argv[1]
token='benchmark-'+'x'*48
with tempfile.TemporaryDirectory() as d:
 env=dict(os.environ,PORT='19878',MCP_TOKEN=token,DATABASE_PATH=d+'/db.sqlite')
 p=subprocess.Popen([binary],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 try:
  time.sleep(.5)
  con=sqlite3.connect(d+'/db.sqlite');desc='Descrição de teste com informações de projeto e detalhes relevantes. '*8
  con.executemany('INSERT INTO items(tipo,titulo,descricao,prazo,concluida) VALUES(?,?,?,?,?)', [('atividade',f'Tarefa {i}',desc,'2028-01-30',i%2) for i in range(1,10001)]);con.commit();con.close()
  def req(method,params):
   payload=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode();r=urllib.request.Request('http://127.0.0.1:19878/mcp',payload,{'Content-Type':'application/json','Authorization':'Bearer '+token})
   start=time.perf_counter_ns()
   with urllib.request.urlopen(r,timeout=5) as x:body=x.read()
   return (time.perf_counter_ns()-start)/1e6,body
  def run(method,params):
   for _ in range(10): req(method,params)
   samples=[req(method,params) for _ in range(150)]; ms=sorted(x[0] for x in samples)
   return {'p50_ms':round(statistics.median(ms),3),'p95_ms':round(ms[int(.95*len(ms))-1],3),'response_bytes':len(samples[-1][1])}
  print(json.dumps({'tools_list':run('tools/list',{}),'listar_padrao':run('tools/call',{'name':'listar_itens','arguments':{}}),'listar_20':run('tools/call',{'name':'listar_itens','arguments':{'limite':20}})},indent=2))
 finally:p.terminate();p.wait()
