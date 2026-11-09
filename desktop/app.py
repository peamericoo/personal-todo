#!/usr/bin/env python3
"""Personal To-Do: cliente GTK para o MCP."""
import json
from datetime import datetime, timezone
import os
import re
import shutil
import subprocess
import time
import threading
import urllib.request
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from tray import Tray
from settings import connection, safe_url

# Give the compositor an application identity instead of the Python executable name.
GLib.set_prgname("personal-todo")
GLib.set_application_name("Personal To-Do")
Gdk.set_program_class("personal-todo")

URL_DEFAULT = ''
CSS = b'''
* { font-family: "Inter", "Noto Sans", sans-serif; font-size: 14px; }
window, .content { background: #17191f; color: #ececf2; }
.sidebar { background: #20222a; border-right: 1px solid #30333c; } .detail { background: #20222a; border-left: 1px solid #30333c; } textview, textview text { background: #30333c; color: #f0f1f7; }
.brand { font-weight: 700; font-size: 15px; color: #f1f1f5; }
.heading { font-weight: 700; font-size: 27px; color: #f5f5fa; }
.subtle { color: #a6a9b6; font-size: 12px; }
.error { color: #ffb4ad; background: #4a282b; padding: 9px; }
button { background: transparent; color: #dbdde6; border: 0; box-shadow: none; text-shadow: none; border-radius: 3px; padding: 7px; }
button:hover { background: #343742; }
button.nav { padding: 10px 12px; }
button.selected { background: #383d50; color: #c7d1ff; }
button.accent { color: #bccaff; }
button.icon { padding: 7px; min-width: 24px; }
entry { color: #f0f1f7; background: #30333c; border: 1px solid #424651; border-radius: 3px; padding: 9px; box-shadow: none; }
entry:focus { border-color: #aabaf4; }
entry placeholder { color: #8d909e; }
.detail entry { background: #24262e; border: 1px solid #343641; padding: 7px 10px; }
.detail entry:focus { border-color: #9daee8; }
.detail textview, .detail textview text { background: #24262e; color: #e7e8ef; }
.detail button.selected { background: #383d50; }
.listrow { background: #24262e; border-radius: 3px; padding: 5px 8px; }
.listrow:hover { background: #2c2f39; } .tagchip { background: #36394c; color: #d1d8ff; border-radius: 4px; padding: 3px 7px; font-size: 11px; } .gridcard { background: #262832; border: 1px solid #383b48; border-radius: 5px; padding: 15px; } .gridcard:hover { background: #2c2f39; }
.tasktitle { font-size: 14px; color: #eeeff4; }
.done { color: #9498a6; text-decoration: line-through; }
checkbutton check { border: 1px solid #a8b4e5; background: transparent; border-radius: 50%; min-width: 17px; min-height: 17px; }
checkbutton:checked check { background: #aebcf5; color: #202332; }
treeview { background: #17191f; color: #dfe1e9; border: 0; }
treeview.view:selected { background: #383d50; color: #e5e9ff; }
scrollbar slider { background: #545764; min-width: 5px; border-radius: 3px; }
'''

def tag_label(text):
    import hashlib
    palette=['#596b9b','#6b5e91','#427e73','#886b42','#8c596b','#536c7d']
    color=palette[hashlib.sha256(text.casefold().encode()).digest()[0]%len(palette)]
    w=label(text,'tagchip');provider=Gtk.CssProvider();provider.load_from_data(('.tagchip { background: '+color+'; color: #ffffff; }').encode());w.get_style_context().add_provider(provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1);return w

def label(text='', style=None):
    w = Gtk.Label(label=text); w.set_xalign(0); w.set_ellipsize(3)
    if style: w.get_style_context().add_class(style)
    return w

def icon_button(icon, callback, tooltip=None):
    b = Gtk.Button(); b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)); b.get_style_context().add_class('icon'); b.connect('clicked', callback)
    if tooltip: b.set_tooltip_text(tooltip)
    def hover(_b,event):
        image=b.get_image(); target=1.0 if event.type==Gdk.EventType.ENTER_NOTIFY else 0.76
        if not Gtk.Settings.get_default().get_property('gtk-enable-animations'): image.set_opacity(target); return False
        initial=image.get_opacity(); start=[None]; b._hover_generation=getattr(b,'_hover_generation',0)+1; generation=b._hover_generation
        def animate(w,clock):
            if generation!=b._hover_generation:return False
            if start[0] is None:start[0]=clock.get_frame_time()
            p=min(1.0,(clock.get_frame_time()-start[0])/140000); image.set_opacity(initial+(target-initial)*p); return p<1
        b.add_tick_callback(animate); return False
    b.get_image().set_opacity(0.76); b.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK|Gdk.EventMask.LEAVE_NOTIFY_MASK); b.connect('enter-notify-event',hover); b.connect('leave-notify-event',hover)
    return b

def nav_button(text, icon, callback):
    b=Gtk.Button(); b.get_style_context().add_class('nav'); row=Gtk.Box(spacing=12); row.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU),False,False,0); row.pack_start(label(text),True,True,0); b.add(row); b.connect('clicked',callback); return b

class Client:
    def __init__(self,url,token): self.url,self.token=url,token
    def call(self,name,args):
        payload=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}},ensure_ascii=False).encode()
        req=urllib.request.Request(self.url,data=payload,headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(req,timeout=30) as response: data=json.load(response)
        if 'error' in data: raise RuntimeError(str(data['error'].get('message','Erro no servidor')))
        result=data['result']; content=result.get('content',[]); raw=content[0].get('text','') if content else '{}'
        if result.get('isError'): raise RuntimeError(raw)
        try: return json.loads(raw)
        except json.JSONDecodeError: raise RuntimeError('Resposta inesperada do servidor')

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title='Personal To-Do'); self.set_icon_from_file(str(Path(__file__).with_name('app-icon.png'))); self.set_default_size(1100,720); self.set_size_request(720,480); self.connect('destroy',Gtk.main_quit); self.connect('delete-event',self.on_close)
        self.client=None; self.items={}; self.details_cache={}; self.selected=None; self.view='tasks'; self.expanded=set(); self.generation=0; self.pending=set(); self.tree_updating=False; self.partial=False; self.layout='list'; self.history_items=[]; self.detail_id=None; self.detail_generation=0
        provider=Gtk.CssProvider(); provider.load_from_data(CSS); Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root=Gtk.Box(); self.add(root)
        self.left_pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL); self.right_pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL); root.pack_start(self.left_pane,True,True,0); self.left_pane.pack2(self.right_pane,True,False); self.widths=self.load_widths(); self.left_pane.connect('notify::position',self.width_changed); self.right_pane.connect('notify::position',self.width_changed); self.right_pane.connect('size-allocate',self.initial_right_width)
        self.side_reveal=Gtk.Revealer(); self.side_reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT); self.side_reveal.set_transition_duration(220); self.side_reveal.set_reveal_child(True); self.side_reveal.get_style_context().add_class('sidebar'); self.left_pane.pack1(self.side_reveal,False,False)
        side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3); side.set_size_request(180,-1); side.set_border_width(14); self.side_reveal.add(side)
        top=Gtk.Box(spacing=8); brand=label('Personal To-Do','brand'); top.pack_start(brand,True,True,5); top.pack_end(icon_button('application-exit-symbolic',lambda *_:self.quit_app(),'Sair'),False,False,0); top.pack_end(icon_button('emblem-system-symbolic',self.connect_dialog,'Conexão'),False,False,0); side.pack_start(top,False,False,10)
        self.search=Gtk.SearchEntry(); self.search.set_placeholder_text('Pesquisar'); self.search.connect('search-changed',lambda *_:self.render_tasks()); side.pack_start(self.search,False,False,5)
        self.nav={}
        for key,title,icon in [('tasks','Tarefas','view-list-symbolic'),('open','Em aberto','document-edit-symbolic'),('done','Concluídas','emblem-ok-symbolic'),('history','Histórico','document-open-recent-symbolic')]:
            b=nav_button(title,icon,lambda _, k=key:self.select_view(k)); self.nav[key]=b; side.pack_start(b,False,False,0)
        sep=Gtk.Separator(); sep.set_margin_top(10); sep.set_margin_bottom(8); side.pack_start(sep,False,False,0)
        cap=Gtk.Box(); cap.pack_start(label('Minhas listas','subtle'),True,True,7); cap.pack_end(icon_button('list-add-symbolic',lambda *_:self.editor(None,'grupo'),'Novo grupo'),False,False,0); side.pack_start(cap,False,False,0)
        self.custom_icons=self.load_icons(); self.model=Gtk.TreeStore(str,str,int); self.tree=Gtk.TreeView(model=self.model); self.tree.set_headers_visible(False); self.tree.set_enable_search(False); self.tree.set_level_indentation(8); self.tree.connect('button-press-event',self.tree_context)
        col=Gtk.TreeViewColumn(); pic=Gtk.CellRendererPixbuf(); col.pack_start(pic,False); col.add_attribute(pic,'icon-name',0); text=Gtk.CellRendererText(); text.set_property('ellipsize',3); text.set_property('ypad',7); text.set_property('xpad',6); col.pack_start(text,True); col.add_attribute(text,'text',1); self.tree.append_column(col)
        self.tree.get_selection().connect('changed',self.on_tree_select); self.tree.connect('row-expanded',self.on_tree_expanded); self.tree.connect('row-collapsed',self.on_tree_collapsed)
        tree_scroll=Gtk.ScrolledWindow(); tree_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC); tree_scroll.add(self.tree); side.pack_start(tree_scroll,True,True,0)
        side.pack_end(icon_button('view-refresh-symbolic',lambda *_:self.sync(),'Atualizar'),False,False,0)
        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0); content.set_border_width(32); content.get_style_context().add_class('content'); self.right_pane.pack1(content,True,False)
        header=Gtk.Box(spacing=8); self.heading=label('Tarefas','heading'); header.pack_start(self.heading,True,True,0); header.pack_start(icon_button('open-menu-symbolic',lambda *_:self.side_reveal.set_reveal_child(not self.side_reveal.get_reveal_child()),'Mostrar ou ocultar listas'),False,False,0); self.list_view=icon_button('view-list-symbolic',lambda *_:self.set_layout('list'),'Visualização em lista'); self.grid_view=icon_button('view-grid-symbolic',lambda *_:self.set_layout('grid'),'Visualização em grade'); header.pack_start(self.list_view,False,False,0); header.pack_start(self.grid_view,False,False,0); self.add_folder=icon_button('folder-new-symbolic',lambda *_:self.editor(None,'pasta'),'Nova pasta'); header.pack_end(self.add_folder,False,False,0); self.edit_selected=icon_button('document-edit-symbolic',lambda *_:self.open_selected(),'Personalizar lista'); header.pack_end(self.edit_selected,False,False,0); content.pack_start(header,False,False,0)
        self.caption=label('','subtle'); self.caption.set_margin_top(6); self.caption.set_margin_bottom(20); content.pack_start(self.caption,False,False,0)
        self.error_label=label('','error'); self.error_label.set_line_wrap(True); content.pack_start(self.error_label,False,False,0)
        self.scroll=Gtk.ScrolledWindow(); self.scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC); content.pack_start(self.scroll,True,True,0)
        self.rows=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3); self.scroll.add(self.rows)
        create=Gtk.Box(spacing=8); create.set_margin_top(12); self.quick=Gtk.Entry(); self.quick.set_placeholder_text('+  Adicionar tarefa'); self.quick.connect('activate',self.quick_add); create.pack_start(self.quick,True,True,0); content.pack_start(create,False,False,0)
        self.detail_reveal=Gtk.Revealer(); self.detail_reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT); self.detail_reveal.set_transition_duration(240); self.detail_reveal.get_style_context().add_class('detail'); self.right_pane.pack2(self.detail_reveal,False,False)
        self.detail=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); self.detail.set_size_request(240,-1); self.detail.set_border_width(18); self.detail_reveal.add(self.detail)
        detail_top=Gtk.Box(); detail_top.pack_start(label('Detalhes','brand'),True,True,0); detail_top.pack_end(icon_button('window-close-symbolic',self.close_detail,'Fechar'),False,False,0); self.detail.pack_start(detail_top,False,False,0)
        self.detail_status=label('','subtle'); self.detail.pack_start(self.detail_status,False,False,0)
        self.detail_fields=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6); self.detail.pack_start(self.detail_fields,True,True,0)
        self.detail_title=Gtk.Entry(); self.detail_title.set_placeholder_text('Nome da tarefa'); self.detail_fields.pack_start(self.detail_title,False,False,0)
        self.detail_fields.pack_start(label('Prazo','subtle'),False,False,0); self.detail_due=Gtk.Entry(); self.detail_due.set_placeholder_text('DD/MM/AAAA'); self.detail_fields.pack_start(self.date_row(self.detail_due,False),False,False,0)
        self.detail_fields.pack_start(label('Tags','subtle'),False,False,0); self.detail_tags=Gtk.Entry(); self.detail_tags.set_placeholder_text('Ex.: aguardando, urgente'); self.detail_fields.pack_start(self.detail_tags,False,False,0)
        self.detail_fields.pack_start(label('Lembrete','subtle'),False,False,0); self.detail_reminder=Gtk.Entry(); self.detail_reminder.set_placeholder_text('DD/MM/AAAA HH:MM'); self.detail_fields.pack_start(self.date_row(self.detail_reminder,True),False,False,0)
        description_header=Gtk.Box(); description_header.pack_start(label('Descrição','subtle'),True,True,0); self.preview_button=Gtk.ToggleButton(label='Prévia'); self.preview_button.connect('toggled',self.toggle_preview); description_header.pack_end(self.preview_button,False,False,0); self.detail_fields.pack_start(description_header,False,False,0)
        toolbar=Gtk.Box(spacing=3);
        for text, start, end in [('H1','# ',''),('B','**','**'),('I','*','*'),('•','- ',''),('</>','`','`')]:
            b=Gtk.Button(label=text); b.get_style_context().add_class('icon'); b.connect('clicked',lambda _b,a=start,z=end:self.insert_markdown(a,z)); toolbar.pack_start(b,False,False,0)
        self.detail_fields.pack_start(toolbar,False,False,0)
        self.description_stack=Gtk.Stack(); self.description_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE); self.description_stack.set_transition_duration(150)
        self.detail_desc=Gtk.TextView(); self.detail_desc.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); self.detail_desc.set_left_margin(8); self.detail_desc.set_right_margin(8); desc_scroll=Gtk.ScrolledWindow(); desc_scroll.set_min_content_height(120); desc_scroll.add(self.detail_desc); self.description_stack.add_named(desc_scroll,'edit')
        self.preview=Gtk.TextView(); self.preview.set_editable(False); self.preview.set_cursor_visible(False); self.preview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); self.preview.set_left_margin(10); self.preview.set_right_margin(10); preview_scroll=Gtk.ScrolledWindow(); preview_scroll.add(self.preview); self.description_stack.add_named(preview_scroll,'preview'); self.detail_fields.pack_start(self.description_stack,True,True,0)
        self.save_detail=Gtk.Button(label='Salvar alterações'); self.save_detail.get_style_context().add_class('selected'); self.save_detail.connect('clicked',self.save_panel); self.detail_fields.pack_start(self.save_detail,False,False,0)
        self.left_pane.set_position(self.widths.get('left',260)); self._width_ready=False; self._width_timer=None; self.show_all(); self.tray=Tray(self); self.error_label.hide(); self.update_nav(); self.render_tasks(); self.detail_reveal.set_reveal_child(False)
        url,token=connection()
        if token and safe_url(url): self.client=Client(url,token); self.sync()
        else: GLib.idle_add(self.connect_dialog)
    def on_close(self,*_):
        if getattr(self,'tray',None) and self.tray.ready:
            self.hide(); return True
        return False
    def quit_app(self):
        if getattr(self,'tray',None):self.tray.close()
        self.destroy()
    def invoke(self,name,args,done,fail=None):
        client=self.client
        if not client: self.error('Abra as configurações de conexão.'); return
        def run():
            try: value=client.call(name,args); GLib.idle_add(done,value)
            except Exception as e: GLib.idle_add(fail or self.error,str(e))
        threading.Thread(target=run,daemon=True).start()
    def error(self,message): self.error_label.set_text(message[:250]); self.error_label.show(); return False
    def clear_error(self): self.error_label.hide()
    def sync(self):
        if not self.client: self.error('Abra as configurações de conexão.'); return
        self.generation+=1; generation=self.generation; client=self.client; self.partial=True; self.details_cache.clear()
        def worker():
            rows=[]; cursor=None
            try:
                while True:
                    args={'limite':100}
                    if cursor is not None: args['cursor']=cursor
                    page=client.call('listar_itens',args); rows.extend(page['itens']); cursor=page.get('proximo_cursor')
                    GLib.idle_add(self.apply_page,generation,list(rows),cursor is not None)
                    if cursor is None: break
            except Exception as e: GLib.idle_add(self.sync_error,generation,str(e))
        threading.Thread(target=worker,daemon=True).start()
    def apply_page(self,generation,rows,more):
        if generation!=self.generation: return False
        self.items={i['id']:i for i in rows}; self.partial=more; self.render_tree(); self.render_tasks(); return False
    def sync_error(self,generation,message):
        if generation==self.generation: self.partial=False; self.error(message); self.render_tasks()
        return False
    def update_nav(self):
        for key,b in self.nav.items():
            ctx=b.get_style_context()
            if self.selected is None and self.view==key: ctx.add_class('selected')
            else: ctx.remove_class('selected')
    def select_view(self,view):
        self.selected=None; self.view=view; self.tree.get_selection().unselect_all(); self.update_nav(); self.render_tasks()
        if view=='history': self.load_history()
    def load_history(self):
        def worker():
            cursor=None; records=[]
            try:
                while True:
                    args={'concluida':True,'tipo':'atividade','detalhes':True,'limite':100}
                    if cursor is not None: args['cursor']=cursor
                    page=self.client.call('listar_itens',args); records.extend(page['itens']); cursor=page.get('proximo_cursor')
                    if cursor is None:break
                GLib.idle_add(self.apply_history,records)
            except Exception as exc: GLib.idle_add(self.error,str(exc))
        if self.client: threading.Thread(target=worker,daemon=True).start()
    def apply_history(self,records):
        for record in records:
            if record['id'] in self.items:self.items[record['id']].update(record)
        if self.view=='history': self.render_tasks()
        return False
    def on_tree_expanded(self,tree,it,path):
        if not self.tree_updating:self.expanded.add(self.model.get_value(it,2))
    def on_tree_collapsed(self,tree,it,path):
        if not self.tree_updating:self.expanded.discard(self.model.get_value(it,2))
    def render_tree(self):
        self.tree_updating=True; self.model.clear(); containers=[i for i in self.items.values() if i['tipo'] in ('grupo','pasta')]; by_parent={}
        for item in containers: by_parent.setdefault(item.get('pai_id'),[]).append(item)
        seen=set()
        def add(parent,rows):
            for item in sorted(rows,key=lambda x:x['titulo'].casefold()):
                if item['id'] in seen: continue
                seen.add(item['id']); choice=self.custom_icons.get(str(item['id']),{}); icon=choice.get('icon') or ('folder-symbolic' if not choice.get('emoji') and item['tipo']=='pasta' else ('folder-open-symbolic' if not choice.get('emoji') else None)); name=(choice.get('emoji','')+'  ' if choice.get('emoji') else '')+item['titulo']; it=self.model.append(parent,[icon,name,item['id']]); path=self.model.get_path(it)
                add(it,by_parent.get(item['id'],[]))
                if item['id'] in self.expanded:self.tree.expand_row(path,False)
                if self.selected==item['id']: self.tree.get_selection().select_iter(it)
        add(None,by_parent.get(None,[]))
        # Orphaned items can occur while a page is still loading.
        if not self.partial: add(None,[i for i in containers if i['id'] not in seen])
        self.tree_updating=False
    def widths_path(self):
        return self.icon_path().with_name('layout.json')
    def load_widths(self):
        try:
            data=json.loads(self.widths_path().read_text()); return {k:max(180,min(600,int(v))) for k,v in data.items() if k in ('left','right')}
        except (OSError,ValueError,TypeError,AttributeError): return {}
    def initial_right_width(self,pane,allocation):
        if not self._width_ready and allocation.width>500:
            self._width_ready=True; pane.set_position(max(300,allocation.width-self.widths.get('right',350)))
    def width_changed(self,pane,*_):
        if not getattr(self,'_width_ready',False):return
        if self._width_timer:GLib.source_remove(self._width_timer)
        self._width_timer=GLib.timeout_add(400,self.persist_widths)
    def persist_widths(self):
        self._width_timer=None
        if not self.get_realized():return False
        self.widths['left']=max(180,min(600,self.left_pane.get_position()))
        if self.detail_reveal.get_reveal_child():self.widths['right']=max(240,min(600,self.right_pane.get_allocated_width()-self.right_pane.get_position()))
        try:
            path=self.widths_path();path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(self.widths));os.chmod(tmp,0o600);tmp.replace(path)
        except OSError as exc:self.error('Não foi possível salvar o layout: '+str(exc))
        return False
    def date_row(self,entry,with_time):
        row=Gtk.Box(spacing=4);row.pack_start(entry,True,True,0)
        b=icon_button('x-office-calendar-symbolic',lambda button:self.calendar_popup(button,entry,with_time),'Escolher data');row.pack_start(b,False,False,0);return row
    def calendar_popup(self,button,entry,with_time):
        pop=Gtk.Popover.new(button);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);box.set_border_width(12);pop.add(box);cal=Gtk.Calendar();box.pack_start(cal,False,False,0)
        try:
            dt=datetime.strptime(entry.get_text().strip(),'%d/%m/%Y %H:%M' if with_time else '%d/%m/%Y');cal.select_month(dt.month-1,dt.year);cal.select_day(dt.day)
        except ValueError:dt=datetime.now()
        hour=Gtk.SpinButton.new_with_range(0,23,1);minute=Gtk.SpinButton.new_with_range(0,59,1);hour.set_value(dt.hour);minute.set_value(dt.minute)
        if with_time:
            line=Gtk.Box(spacing=5);line.pack_start(label('Horário'),False,False,0);line.pack_start(hour,False,False,0);line.pack_start(label(':'),False,False,0);line.pack_start(minute,False,False,0);box.pack_start(line,False,False,0)
        def apply(_):
            year,month,day=cal.get_date();value=f'{day:02d}/{month+1:02d}/{year:04d}'
            if with_time:value+=f' {hour.get_value_as_int():02d}:{minute.get_value_as_int():02d}'
            entry.set_text(value);pop.popdown()
        ok=Gtk.Button(label='Aplicar');ok.connect('clicked',apply);box.pack_start(ok,False,False,0);pop.show_all();pop.popup()
    def task_key(self,widget,event,item):
        if event.keyval==Gdk.KEY_space:self.quick_preview(item);return True
        return False
    def quick_preview(self,item):
        def loaded(data):
            value=data['item'];dialog=Gtk.Dialog(title=value['titulo'],transient_for=self,flags=Gtk.DialogFlags.MODAL);dialog.set_default_size(850,650);dialog.add_button('Fechar',Gtk.ResponseType.CLOSE);dialog.add_button('Editar',Gtk.ResponseType.OK)
            box=dialog.get_content_area();box.set_border_width(24);scroll=Gtk.ScrolledWindow();view=Gtk.TextView();view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);view.set_editable(False);view.set_cursor_visible(False);self.render_markdown(value.get('descricao') or 'Sem descrição.',view);scroll.add(view);box.pack_start(scroll,True,True,0);dialog.show_all();response=dialog.run();dialog.destroy()
            if response==Gtk.ResponseType.OK:self.show_detail(item)
            return False
        self.invoke('obter_item',{'id':item['id'],'limite':1},loaded)
    def delete_container(self,item):
        d=Gtk.MessageDialog(transient_for=self,flags=Gtk.DialogFlags.MODAL,message_type=Gtk.MessageType.WARNING,buttons=Gtk.ButtonsType.NONE,text='Excluir grupo ou lista?');d.format_secondary_text('Todas as pastas, tarefas e subtarefas dentro deste item serão excluídas permanentemente.');d.add_button('Cancelar',Gtk.ResponseType.CANCEL);d.add_button('Excluir tudo',Gtk.ResponseType.OK);answer=d.run();d.destroy()
        if answer==Gtk.ResponseType.OK:
            def done(_):
                self.selected=None;self.close_detail();self.sync();return False
            self.invoke('excluir_item',{'id':item['id'],'confirmar':True},done)
    def icon_path(self):
        return Path(os.getenv('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'personal-todo'/'icons.json'
    def load_icons(self):
        try:
            data=json.loads(self.icon_path().read_text()); return data if isinstance(data,dict) else {}
        except (OSError,ValueError):return {}
    def tree_context(self,tree,event):
        if event.button!=3:return False
        pos=tree.get_path_at_pos(int(event.x),int(event.y))
        if not pos:return False
        path=pos[0]; tree.set_cursor(path); item_id=self.model.get_value(self.model.get_iter(path),2); self.icon_dialog(item_id); return True
    def icon_dialog(self,item_id):
        item=self.items.get(item_id)
        if not item:return
        d=Gtk.Dialog(title='Personalizar lista',transient_for=self,flags=Gtk.DialogFlags.MODAL);d.add_button('Cancelar',Gtk.ResponseType.CANCEL);d.add_button('Excluir',Gtk.ResponseType.REJECT);d.add_button('Salvar',Gtk.ResponseType.OK);d.set_default_size(360,180);box=d.get_content_area();box.set_border_width(18);box.set_spacing(8)
        box.add(label('Nome da lista','subtle')); name=Gtk.Entry(); name.set_text(item['titulo']); box.add(name)
        box.add(label('Ícone ou emoji','subtle')); picker=Gtk.Box(spacing=5); box.add(picker)
        choices=[('Pasta','folder-symbolic'),('Pasta aberta','folder-open-symbolic'),('Estrela','starred-symbolic'),('Marcador','bookmark-new-symbolic'),('Projetos','applications-engineering-symbolic')]
        saved=self.custom_icons.get(str(item_id),{}); selected={'icon':saved.get('icon',choices[0][1]),'emoji':saved.get('emoji','')}
        for title,icon in choices:
            b=Gtk.Button();b.set_image(Gtk.Image.new_from_icon_name(icon,Gtk.IconSize.MENU));b.set_tooltip_text(title);b.connect('clicked',lambda _b,i=icon:selected.update(icon=i,emoji=''));picker.pack_start(b,False,False,0)
        emoji_button=Gtk.Button(label='😊');emoji_button.set_tooltip_text('Escolher emoji');picker.pack_start(emoji_button,False,False,0)
        emoji_entry=Gtk.Entry();emoji_entry.set_width_chars(3);emoji_entry.set_placeholder_text('😊');picker.pack_start(emoji_entry,False,False,0);emoji_button.connect('clicked',lambda *_:emoji_entry.emit('insert-emoji'));emoji_entry.connect('changed',lambda e:selected.update(emoji=e.get_text(),icon='') if e.get_text() else None)
        d.show_all();answer=d.run();new_name=name.get_text().strip();value=selected['emoji'];chosen=selected['icon'];d.destroy()
        if answer==Gtk.ResponseType.REJECT:
            self.delete_container(item); return
        if answer==Gtk.ResponseType.OK:
            if not new_name:self.error('Informe um nome.');return
            if new_name!=item['titulo']:self.invoke('atualizar_item',{'id':item_id,'titulo':new_name},lambda result:self.upsert(result))
            self.custom_icons[str(item_id)]={'emoji':value,'icon':chosen}
            try:
                path=self.icon_path();path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(self.custom_icons,ensure_ascii=False));os.chmod(tmp,0o600);tmp.replace(path);self.render_tree()
            except OSError as e:self.error('Não foi possível salvar o ícone: '+str(e))
    def on_tree_select(self,selection):
        if self.tree_updating:return
        model,it=selection.get_selected()
        if it: self.selected=model.get_value(it,2); self.update_nav(); self.render_tasks()
    def render_tasks(self):
        for child in self.rows.get_children(): self.rows.remove(child)
        selected=self.items.get(self.selected); self.heading.set_text(selected['titulo'] if selected else {'tasks':'Tarefas','open':'Em aberto','done':'Concluídas','history':'Histórico'}[self.view]); self.edit_selected.set_visible(bool(selected)); self.edit_selected.set_sensitive(bool(selected)); self.add_folder.set_sensitive(not selected or selected['tipo'] in ('grupo','pasta'))
        query=self.search.get_text().strip().casefold(); self.list_view.get_style_context().remove_class('selected'); self.grid_view.get_style_context().remove_class('selected'); (self.list_view if self.layout=='list' else self.grid_view).get_style_context().add_class('selected'); tasks=[i for i in self.items.values() if i['tipo']=='atividade']
        if selected: tasks=[i for i in tasks if i.get('pai_id')==selected['id'] or self.is_descendant(i,selected['id'])]
        elif self.view=='open': tasks=[i for i in tasks if not i.get('concluida')]
        elif self.view in ('done','history'): tasks=[i for i in tasks if i.get('concluida')]
        if query: tasks=[i for i in tasks if query in i['titulo'].casefold() or any(query in t.casefold() for t in i.get('tags',[]))]
        ids={i['id'] for i in tasks}; by_parent={}
        for item in tasks: by_parent.setdefault(item.get('pai_id') if item.get('pai_id') in ids else None,[]).append(item)
        self.caption.set_text('Carregando…' if self.partial else (f'{len(tasks)} '+('tarefa' if len(tasks)==1 else 'tarefas')))
        if self.layout=='grid':
            grid=Gtk.FlowBox(); grid.set_selection_mode(Gtk.SelectionMode.NONE); grid.set_homogeneous(True); grid.set_min_children_per_line(1); grid.set_max_children_per_line(3); grid.set_row_spacing(8); grid.set_column_spacing(8)
            for item in sorted(tasks,key=lambda x:(bool(x.get('concluida')),x['titulo'].casefold())):
                card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); card.set_size_request(210,125); card.get_style_context().add_class('gridcard'); top=Gtk.Box(spacing=8); ck=Gtk.CheckButton(); ck.set_active(bool(item.get('concluida'))); ck.set_sensitive(item['id'] not in self.pending); ck.connect('toggled',self.toggle,item); top.pack_start(ck,False,False,0); top.pack_end(icon_button('document-edit-symbolic',lambda _,i=item:self.show_detail(i),'Detalhes'),False,False,0); card.pack_start(top,False,False,0)
                name=label(item['titulo'],'tasktitle'); name.set_line_wrap(True); name.set_ellipsize(0); name.set_max_width_chars(28); click=Gtk.EventBox(); click.add(name); click.connect('button-press-event',lambda _w,_e,i=item:self.show_detail(i)); card.pack_start(click,True,True,0)
                info=Gtk.Box(spacing=4); info.pack_start(label(item.get('prazo') or '', 'subtle'),False,False,0)
                for tag in item.get('tags',[])[:3]: info.pack_start(tag_label(tag),False,False,0)
                card.pack_start(info,False,False,0); grid.add(card)
            self.rows.pack_start(grid,False,False,0); self.rows.show_all(); return
        def add(parent,depth,container):
            for item in sorted(by_parent.get(parent,[]),key=lambda x:(bool(x.get('concluida')),x['titulo'].casefold())):
                row=Gtk.Box(spacing=8); row.get_style_context().add_class('listrow'); row.set_margin_start(min(depth*24,120))
                children=by_parent.get(item['id'],[])
                if children:
                    expanded=item['id'] in self.expanded; arrow=Gtk.Button(); arrow.get_style_context().add_class('icon'); icons=Gtk.Stack(); icons.set_transition_type(Gtk.StackTransitionType.CROSSFADE); icons.set_transition_duration(160); icons.add_named(Gtk.Image.new_from_icon_name('pan-end-symbolic',Gtk.IconSize.MENU),'closed'); icons.add_named(Gtk.Image.new_from_icon_name('pan-down-symbolic',Gtk.IconSize.MENU),'open'); icons.set_visible_child_name('open' if expanded else 'closed'); arrow.add(icons); row.pack_start(arrow,False,False,0)
                else:
                    spacer=Gtk.Box(); spacer.set_size_request(24,-1); row.pack_start(spacer,False,False,0)
                ck=Gtk.CheckButton(); ck.set_active(bool(item.get('concluida'))); ck.set_sensitive(item['id'] not in self.pending); ck.connect('toggled',self.toggle,item); row.pack_start(ck,False,False,0)
                name=label(item['titulo'],'tasktitle'); name.set_margin_top(8); name.set_margin_bottom(8)
                if item.get('concluida'): name.get_style_context().add_class('done')
                task_click=Gtk.EventBox(); task_click.set_can_focus(True); task_click.add(name); task_click.connect('button-press-event',lambda w,_e,i=item:(w.grab_focus(),self.show_detail(i))[1]); task_click.connect('key-press-event',self.task_key,item); row.pack_start(task_click,True,True,0)
                for tag in item.get('tags',[])[:3]: row.pack_start(tag_label(tag),False,False,2)
                if self.view=='history' and item.get('atualizado_em_utc'): row.pack_start(label('Atualizada: '+item['atualizado_em_utc'][:10],'subtle'),False,False,6)
                elif item.get('prazo'): row.pack_start(label(item['prazo'],'subtle'),False,False,6)
                if item.get('lembrete_utc'):
                    bell=Gtk.Image.new_from_icon_name('alarm-symbolic',Gtk.IconSize.MENU); bell.set_tooltip_text('Esta tarefa tem lembrete'); row.pack_start(bell,False,False,3)
                row.pack_end(icon_button('document-edit-symbolic',lambda _,i=item:self.show_detail(i),'Detalhes'),False,False,0)
                row.pack_end(icon_button('list-add-symbolic',lambda _,i=item:self.editor(None,'atividade',i),'Adicionar subtarefa'),False,False,0)
                container.pack_start(row,False,False,0)
                if children:
                    reveal=Gtk.Revealer(); reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN); reveal.set_transition_duration(200); nested=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3); reveal.add(nested); container.pack_start(reveal,False,False,0); add(item['id'],depth+1,nested); reveal.set_reveal_child(expanded)
                    arrow.connect('clicked',self.toggle_expand,item,reveal,icons)
        add(None,0,self.rows)
        if not tasks and not self.partial:
            empty=label('Nenhuma tarefa aqui.','subtle'); empty.set_margin_top(25); self.rows.pack_start(empty,False,False,0)
        self.rows.show_all()
    def set_layout(self,layout):
        self.layout=layout; self.render_tasks()
    def is_descendant(self,item,parent):
        seen=set(); current=item.get('pai_id')
        while current and current not in seen:
            if current==parent:return True
            seen.add(current); current=self.items.get(current,{}).get('pai_id')
        return False
    def toggle_expand(self,_button,item,reveal,icons):
        opening=not reveal.get_reveal_child()
        if opening:self.expanded.add(item['id'])
        else:self.expanded.discard(item['id'])
        icons.set_visible_child_name('open' if opening else 'closed'); reveal.set_reveal_child(opening)
    def toggle(self,widget,item):
        desired=widget.get_active(); old=bool(item.get('concluida')); item['concluida']=desired; self.pending.add(item['id']); self.generation+=1; widget.set_sensitive(False)
        started=[None]; animating=[True]
        def frame(w,clock):
            if started[0] is None:started[0]=clock.get_frame_time()
            progress=min(1.0,(clock.get_frame_time()-started[0])/260000); w.set_opacity(0.55+0.45*abs(2*progress-1))
            if progress>=1:animating[0]=False;self.render_tasks();return False
            return True
        if Gtk.Settings.get_default().get_property('gtk-enable-animations'):widget.add_tick_callback(frame)
        else:animating[0]=False;self.render_tasks()
        def done(result):
            if desired:
                self.play_completion()
            self.pending.discard(item['id']); self.items[item['id']].update(result); self.details_cache.pop(item['id'],None);
            if not animating[0]: self.render_tasks()
            if self.partial and not self.pending: self.sync()
            return False
        def fail(msg):
            self.pending.discard(item['id']); item['concluida']=old; self.render_tasks(); self.error(msg)
            if self.partial and not self.pending: self.sync()
            return False
        self.invoke('atualizar_item',{'id':item['id'],'concluida':desired},done,fail)
    def play_completion(self):
        if os.getenv('TODO_SOUND','1')=='0':return
        sound=str(Path(__file__).with_name('complete.wav')); player=shutil.which('paplay') or shutil.which('pw-play')
        if player:
            try:subprocess.Popen([player,sound],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            except OSError:pass
    def quick_add(self,entry):
        title=entry.get_text().strip()
        if not title:return
        parent=self.items.get(self.selected)
        if parent and parent['tipo']=='grupo': self.error('Selecione uma pasta para adicionar tarefas a este grupo.'); return
        args={'tipo':'atividade','titulo':title}
        if parent:args['pai_id']=parent['id']
        entry.set_sensitive(False)
        def done(item): entry.set_sensitive(True); entry.set_text(''); self.upsert(item); entry.grab_focus(); return False
        def fail(msg):entry.set_sensitive(True); self.error(msg); return False
        self.invoke('criar_item',args,done,fail)
    def upsert(self,item):
        self.generation+=1; self.items[item['id']]=item; self.details_cache[item['id']]=item; self.clear_error(); self.render_tree(); self.render_tasks()
        if self.partial and not self.pending: self.sync()
    def close_detail(self,*_):
        self.detail_generation+=1; self.detail_id=None; self.detail_reveal.set_reveal_child(False)
    def show_detail(self,item):
        self.detail_generation+=1; gen=self.detail_generation; self.detail_id=item['id']; self.detail_title.set_text(item['titulo']); self.detail_due.set_text(item.get('prazo') or ''); self.detail_reminder.set_text(''); self.detail_tags.set_text(''); self.detail_desc.get_buffer().set_text(''); self.detail_status.set_text('Carregando…'); self.detail_fields.set_sensitive(False); self.preview_button.set_active(False); self.detail_reveal.set_reveal_child(True)
        def loaded(data):
            if self.detail_id != item['id'] or gen!=self.detail_generation: return False
            value=data['item']; self.details_cache[item['id']]=value; self.detail_title.set_text(value['titulo']); self.detail_due.set_text(value.get('prazo') or ''); self.detail_desc.get_buffer().set_text(value.get('descricao') or '')
            raw=value.get('lembrete_utc')
            try: display=datetime.fromisoformat(raw.replace('Z','+00:00')).astimezone().strftime('%d/%m/%Y %H:%M') if raw else ''
            except ValueError: display=''
            self.detail_reminder.set_text(display); self.detail_tags.set_text(', '.join(value.get('tags',[]))); self.detail_status.set_text(''); self.detail_fields.set_sensitive(True); return False
        def failed(message):
            if self.detail_id==item['id'] and gen==self.detail_generation: self.detail_status.set_text('Não foi possível carregar.'); self.error(message)
            return False
        self.invoke('obter_item',{'id':item['id'],'limite':1},loaded,failed)
        return False
    def insert_markdown(self,start,end):
        self.preview_button.set_active(False); buf=self.detail_desc.get_buffer(); selection=buf.get_selection_bounds()
        if selection:
            a,b=selection; selected=buf.get_text(a,b,True); buf.delete(a,b); buf.insert_at_cursor(start+selected+end)
        else: buf.insert_at_cursor(start+end)
        self.detail_desc.grab_focus()
    def toggle_preview(self,button):
        if not button.get_active(): self.description_stack.set_visible_child_name('edit'); return
        src=self.detail_desc.get_buffer(); text=src.get_text(src.get_start_iter(),src.get_end_iter(),True); self.render_markdown(text,self.preview); self.description_stack.set_visible_child_name('preview')
    def render_markdown(self,text,view):
        from markdown_view import render
        if render(text,view):return
        buf=view.get_buffer(); buf.set_text('')
        tags=buf.get_tag_table()
        for name,props in [('heading',{'weight':700,'scale':1.3,'pixels-above-lines':8,'pixels-below-lines':5}),('heading2',{'weight':700,'scale':1.14,'pixels-above-lines':6,'pixels-below-lines':3}),('bold',{'weight':700}),('italic',{'style':2}),('link',{'foreground':'#aebcf5','underline':1}),('code',{'family':'monospace','background':'#292c35'}),('quote',{'foreground':'#b7c1e8','left-margin':12})]:
            if not tags.lookup(name):buf.create_tag(name,**props)
        in_code=False
        for line in text.splitlines(keepends=True):
            if line.strip().startswith('```'): in_code=not in_code; continue
            tag=None; content=line
            if in_code:tag='code'
            elif re.match(r'^#{1,6}\s+',line): tag='heading' if line.startswith('# ') else 'heading2'; content=re.sub(r'^#{1,6}\s+','',line)
            elif re.match(r'^\s*[-*]\s+\[[ xX]\]\s+',line): content=re.sub(r'^(\s*)[-*]\s+\[([ xX])\]\s+',lambda m:m.group(1)+('☑  ' if m.group(2).lower()=='x' else '☐  '),line)
            elif re.match(r'^\s*[-*]\s+',line): content=re.sub(r'^(\s*)[-*]\s+',r'\1•  ',line)
            elif line.startswith('> '):tag='quote';content=line[2:]
            # Insert text as text, never as markup; untrusted descriptions cannot inject UI markup.
            pieces=re.split(r'(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*|`[^`]+`|\[[^]]+\]\([^)]+\))',content)
            for part in pieces:
                inline='bold' if part.startswith('**') and part.endswith('**') else ('italic' if part.startswith('*') and part.endswith('*') else ('code' if part.startswith('`') and part.endswith('`') else ('link' if re.fullmatch(r'\[[^]]+\]\([^)]+\)',part) else tag)))
                if inline=='bold' and part.startswith('**'):part=part[2:-2]
                elif inline=='code' and part.startswith('`') and part.endswith('`'):part=part[1:-1]
                elif inline=='italic':part=part[1:-1]
                elif inline=='link':part=re.sub(r'^\[([^]]+)\]\(([^)]+)\)$',r'\1 (\2)',part)
                if inline:buf.insert_with_tags_by_name(buf.get_end_iter(),part,inline)
                else:buf.insert(buf.get_end_iter(),part)
    def save_panel(self,*_):
        item_id=self.detail_id
        if not item_id: return
        title=self.detail_title.get_text().strip(); due=self.detail_due.get_text().strip(); raw=self.detail_reminder.get_text().strip(); buffer=self.detail_desc.get_buffer(); description=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True).strip()
        if not title: self.detail_status.set_text('Informe um título.'); return
        try:
            if due: datetime.strptime(due,'%d/%m/%Y')
            reminder=datetime.strptime(raw,'%d/%m/%Y %H:%M').astimezone().astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z') if raw else None
        except ValueError: self.detail_status.set_text('Confira a data e o horário.'); return
        tags=[t.strip() for t in self.detail_tags.get_text().split(',') if t.strip()];
        if len(tags)>3: self.detail_status.set_text('Use no máximo 3 tags por atividade.'); return
        args={'id':item_id,'titulo':title,'prazo':due or None,'descricao':description or None,'lembrete_utc':reminder,'tags':tags}; self.detail_fields.set_sensitive(False); self.detail_status.set_text('Salvando…')
        def done(value):
            self.upsert(value)
            if self.detail_id==item_id: self.detail_status.set_text('Salvo'); self.detail_fields.set_sensitive(True)
            return False
        def fail(message):
            if self.detail_id==item_id:self.detail_status.set_text('Não foi possível salvar.'); self.detail_fields.set_sensitive(True)
            self.error(message); return False
        self.invoke('atualizar_item',args,done,fail)
    def open_selected(self):
        if self.selected in self.items:self.icon_dialog(self.selected)
    def details(self,item):
        if item['id'] in self.details_cache:self.editor(self.details_cache[item['id']]); return
        self.invoke('obter_item',{'id':item['id'],'limite':1},lambda data:self.editor(data['item']))
    def editor(self,item=None,kind='atividade',parent_override=None):
        edit=item is not None; parent=parent_override or self.items.get(self.selected)
        d=Gtk.Dialog(title='Editar' if edit else 'Novo item',transient_for=self,flags=Gtk.DialogFlags.MODAL); d.set_default_size(450,280); d.add_button('Cancelar',Gtk.ResponseType.CANCEL)
        if edit:d.add_button('Excluir',Gtk.ResponseType.REJECT)
        d.add_button('Salvar',Gtk.ResponseType.OK); box=d.get_content_area(); box.set_border_width(20); box.set_spacing(8)
        box.add(label('Título','subtle')); title=Gtk.Entry(); title.set_text(item.get('titulo','') if edit else ''); box.add(title)
        if edit: kind=item['tipo']
        box.add(label('Prazo (DD/MM/AAAA)','subtle')); due=Gtk.Entry(); due.set_text((item.get('prazo') or '') if edit else ''); due.set_sensitive(kind=='atividade'); box.add(due)
        box.add(label('Descrição','subtle')); desc=Gtk.Entry(); desc.set_text((item.get('descricao') or '') if edit else ''); box.add(desc); d.show_all(); response=d.run(); name=title.get_text().strip(); date=due.get_text().strip(); description=desc.get_text().strip(); d.destroy()
        if response==Gtk.ResponseType.REJECT and edit:
            confirm=Gtk.MessageDialog(transient_for=self,flags=Gtk.DialogFlags.MODAL,message_type=Gtk.MessageType.WARNING,buttons=Gtk.ButtonsType.NONE,text='Excluir este item?'); confirm.format_secondary_text('Todos os itens dentro dele também serão excluídos permanentemente.'); confirm.add_button('Cancelar',Gtk.ResponseType.CANCEL); confirm.add_button('Excluir',Gtk.ResponseType.OK); answer=confirm.run(); confirm.destroy()
            if answer==Gtk.ResponseType.OK:
                def deleted(_):
                    self.generation+=1; self.items={k:v for k,v in self.items.items() if k!=item['id'] and not self.is_descendant(v,item['id'])}; self.details_cache.clear(); self.selected=None; self.render_tree(); self.render_tasks(); return False
                self.invoke('excluir_item',{'id':item['id'],'confirmar':True},deleted)
        elif response==Gtk.ResponseType.OK:
            if not name:self.error('Informe um título.'); return False
            args={'titulo':name,'prazo':date or None,'descricao':description or None}
            if edit: args['id']=item['id']
            else:
                args['tipo']=kind
                if parent and kind!='grupo':args['pai_id']=parent['id']
            self.invoke('atualizar_item' if edit else 'criar_item',args,lambda result:self.upsert(result))
        return False
    def connect_dialog(self,*_):
        d=Gtk.Dialog(title='Conexão',transient_for=self,flags=Gtk.DialogFlags.MODAL); d.add_button('Cancelar',Gtk.ResponseType.CANCEL); d.add_button('Conectar',Gtk.ResponseType.OK); box=d.get_content_area(); box.set_spacing(10); box.set_border_width(20); d.set_default_size(480,180)
        box.add(label('Endereço do servidor','subtle')); url=Gtk.Entry(); url.set_text(self.client.url if self.client else os.getenv('TODO_MCP_URL',URL_DEFAULT)); box.add(url)
        box.add(label('Chave de acesso','subtle')); token=Gtk.Entry(); token.set_visibility(False); box.add(token); d.show_all(); response=d.run(); u=url.get_text().strip(); t=token.get_text().strip(); d.destroy()
        if response==Gtk.ResponseType.OK:
            from urllib.parse import urlparse
            parts=urlparse(u)
            if parts.scheme!='https' and not (parts.scheme=='http' and parts.hostname in ('localhost','127.0.0.1')):self.error('Use HTTPS para conexões remotas.'); return False
            if not t:self.error('Informe a chave de acesso.'); return False
            self.client=Client(u,t); self.items={}; self.details_cache={}; self.selected=None; self.sync()
        return False

def main():
    bus=None; registration=None; holder={}
    try:
        bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        name='org.peamericoo.PersonalTodo'
        reply=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','RequestName',GLib.Variant('(su)',(name,4)),GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,1000,None)
        if reply.unpack()[0]!=1:
            bus.call_sync(name,'/org/peamericoo/PersonalTodo','org.peamericoo.PersonalTodo','Open',None,None,Gio.DBusCallFlags.NONE,1500,None); return
        xml='<node><interface name="org.peamericoo.PersonalTodo"><method name="Open"/></interface></node>'
        def open_window(_c,_s,_p,_i,_m,_a,invocation):
            app=holder.get('app')
            if app:app.show();app.present()
            invocation.return_value(None)
        registration=bus.register_object('/org/peamericoo/PersonalTodo',Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],open_window,None,None)
    except Exception: pass
    holder['app']=App(); Gtk.main()
    if bus and registration:bus.unregister_object(registration)

if __name__=='__main__': main()
