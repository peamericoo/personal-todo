#!/usr/bin/env python3
"""Cliente mínimo: python3 todo.py listar_itens '{}'"""
import json, os, sys, urllib.request, urllib.error
url=os.environ.get('TODO_MCP_URL')
token=os.environ.get('TODO_MCP_TOKEN')
if not url:
    sys.exit('Defina TODO_MCP_URL com o endereço MCP.')
if not token:
    sys.exit('Defina TODO_MCP_TOKEN com a chave de acesso.')
if len(sys.argv) not in (2,3):
    sys.exit('Uso: python3 todo.py NOME_DA_FERRAMENTA \'{"argumento":"valor"}\'')
try:
    args=json.loads(sys.argv[2]) if len(sys.argv)==3 else {}
    payload=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':sys.argv[1],'arguments':args}}).encode()
    request=urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Authorization':'Bearer '+token})
    with urllib.request.urlopen(request,timeout=60) as response: result=json.load(response)
    if 'error' in result: raise ValueError(result['error'])
    out=result['result']; content=out['content'][0]['text']
    try: print(json.dumps(json.loads(content),ensure_ascii=False,indent=2))
    except json.JSONDecodeError: print(content)
    if out.get('isError'): sys.exit(1)
except (ValueError, urllib.error.URLError) as e: sys.exit(str(e))
