import sys
sys.path.insert(0, "desktop")
import os,tempfile,subprocess,time,urllib.request,importlib.util,statistics
os.environ['TODO_MCP_TOKEN']='test-'+'x'*48;os.environ['TODO_MCP_URL']='http://127.0.0.1:19887/mcp'
tmp=tempfile.TemporaryDirectory();p=subprocess.Popen(['target/release/personal-todo'],env=dict(os.environ,PORT='19887',MCP_TOKEN=os.environ['TODO_MCP_TOKEN'],DATABASE_PATH=tmp.name+'/db'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(100):
  try:urllib.request.urlopen('http://127.0.0.1:19887/health',timeout=1);break
  except Exception:time.sleep(.05)
 spec=importlib.util.spec_from_file_location('app','desktop/app.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);c=m.Client(os.environ['TODO_MCP_URL'],os.environ['TODO_MCP_TOKEN'])
 for i in range(40):c.call('criar_item',{'tipo':'atividade','titulo':f'Tarefa de teste {i}'})
 app=m.App();samples=[];active=[False]
 def tick(widget,clock):
  if active[0]:samples.append(clock.get_frame_time())
  return True
 app.add_tick_callback(tick)
 def start():active[0]=True;app.side_reveal.set_reveal_child(False);m.GLib.timeout_add(220,stop);return False
 def stop():
  active[0]=False;gaps=[(b-a)/1000 for a,b in zip(samples,samples[1:]) if b>a];print('quadros:',len(samples),'mediana ms:',round(statistics.median(gaps),1) if gaps else 'sem dados','máximo ms:',round(max(gaps),1) if gaps else 'sem dados',flush=True);m.Gtk.main_quit();return False
 m.GLib.timeout_add(900,start);m.Gtk.main()
finally:p.terminate();p.wait();tmp.cleanup()
