import sys
sys.path.insert(0, "desktop")
import os,tempfile,subprocess,time,urllib.request,importlib.util
os.environ['TODO_SOUND']='0';os.environ['TODO_MCP_TOKEN']='test-'+'x'*48;os.environ['TODO_MCP_URL']='http://127.0.0.1:19886/mcp'
tmp=tempfile.TemporaryDirectory();p=subprocess.Popen(['target/release/personal-todo'],env=dict(os.environ,PORT='19886',MCP_TOKEN=os.environ['TODO_MCP_TOKEN'],DATABASE_PATH=tmp.name+'/db'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
 for _ in range(100):
  try:urllib.request.urlopen('http://127.0.0.1:19886/health',timeout=1);break
  except Exception:time.sleep(.05)
 spec=importlib.util.spec_from_file_location('app','desktop/app.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);client=m.Client(os.environ['TODO_MCP_URL'],os.environ['TODO_MCP_TOKEN']);item=client.call('criar_item',{'tipo':'atividade','titulo':'Uma tarefa','descricao':'Original'});child=client.call('criar_item',{'tipo':'atividade','titulo':'Subtarefa','pai_id':item['id']});app=m.App()
 class Invocation:
  def return_value(self,value): pass
 def openit():
  try:
   assert item['id'] in app.items; assert app.tray.ready; assert app.on_close() is True; assert not app.get_visible();
   app.tray.method(None,None,None,None,'Activate',None,Invocation()); assert app.get_visible(); assert len(app.rows.get_children()) == 2; row,reveal=app.rows.get_children(); assert not reveal.get_reveal_child(); row.get_children()[0].clicked(); assert reveal.get_reveal_child(); row.get_children()[0].clicked(); assert not reveal.get_reveal_child(); app.show_detail(app.items[item['id']]);m.GLib.timeout_add(500,edit)
  except Exception as e:print('FALHOU',repr(e),flush=True);os._exit(1)
  return False
 def edit():
  try:
   assert app.detail.get_visible() and app.detail_fields.get_sensitive(); assert app.detail_title.get_text()=='Uma tarefa';app.set_layout('grid'); assert app.layout=='grid'; app.set_layout('list'); app.detail_tags.set_text('Urgente, Suporte'); app.detail_due.set_text('10/11/2026');app.detail_reminder.set_text('10/11/2026 14:30');app.detail_desc.get_buffer().set_text('# Título\n- **Descrição editada**\n[Link](https://example.com)'); app.preview_button.set_active(True); preview=app.preview.get_buffer(); assert 'Descrição editada' in preview.get_text(preview.get_start_iter(),preview.get_end_iter(),True); app.preview_button.set_active(False); app.side_reveal.set_reveal_child(False); assert not app.side_reveal.get_reveal_child(); app.side_reveal.set_reveal_child(True); app.save_panel();m.GLib.timeout_add(500,verify)
  except Exception as e:print('FALHOU',repr(e),flush=True);os._exit(1)
  return False
 def verify():
  try:
   saved=client.call('obter_item',{'id':item['id']})['item'];assert 'Descrição editada' in saved['descricao'] and saved['prazo']=='10/11/2026' and saved['lembrete_utc'] and saved['tags']==['Urgente','Suporte']; row=app.rows.get_children()[0]; check=next(w for w in row.get_children() if isinstance(w,m.Gtk.CheckButton)); check.set_active(True); m.GLib.timeout_add(700,history)
  except Exception as e:print('FALHOU',repr(e),flush=True);os._exit(1)
  return False
 def history():
  try:
   assert client.call('obter_item',{'id':item['id']})['item']['concluida']; app.select_view('history'); m.GLib.timeout_add(500,history_done)
  except Exception as e: print('FALHOU',repr(e),flush=True);os._exit(1)
  return False
 def history_done():
  try:
   assert app.items[item['id']]['atualizado_em_utc']; assert app.view=='history'; print('OK: painel, tags, histórico e conclusão',flush=True);m.Gtk.main_quit()
  except Exception as e:print('FALHOU',repr(e),flush=True);os._exit(1)
  return False
 m.GLib.timeout_add(700,openit);m.Gtk.main()
finally:p.terminate();p.wait();tmp.cleanup()
