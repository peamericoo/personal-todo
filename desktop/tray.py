"""Bandeja StatusNotifierItem e menu D-Bus para KDE e hosts compatíveis."""
from pathlib import Path
from gi.repository import Gio, GLib

XML='''<node><interface name="org.kde.StatusNotifierItem">
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method><method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method><method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method><method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/><property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/><property name="IconName" type="s" access="read"/><property name="ItemIsMenu" type="b" access="read"/><property name="Menu" type="o" access="read"/><signal name="NewIcon"/><signal name="NewStatus"><arg type="s"/></signal></interface></node>'''
MENU='''<node><interface name="com.canonical.dbusmenu"><property name="Version" type="u" access="read"/><property name="TextDirection" type="s" access="read"/><property name="Status" type="s" access="read"/><property name="IconThemePath" type="as" access="read"/><method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method><method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method><method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method><method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method><signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal></interface></node>'''
class Tray:
 def __init__(self,window):
  self.window=window;self.ready=False;self.connection=None;self.reg=None;self.menu_reg=None
  try:
   self.connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
   host=self.connection.call_sync('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.kde.StatusNotifierWatcher','IsStatusNotifierHostRegistered')),None,Gio.DBusCallFlags.NONE,1000,None)
   if not host.unpack()[0]: return
   self.reg=self.connection.register_object('/StatusNotifierItem',Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],self.method,self.get_property,None)
   self.menu_reg=self.connection.register_object('/Menu',Gio.DBusNodeInfo.new_for_xml(MENU).interfaces[0],self.menu_method,self.menu_property,None)
   self.connection.call_sync('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.kde.StatusNotifierWatcher','RegisterStatusNotifierItem',GLib.Variant('(s)',(self.connection.get_unique_name(),)),None,Gio.DBusCallFlags.NONE,1000,None);self.ready=True
  except Exception as e: print('Bandeja indisponível:',type(e).__name__)
 def get_property(self,_conn,_sender,_path,_interface,name):
  values={'Category':'ApplicationStatus','Id':'personal-todo','Title':'Personal To-Do','Status':'Active','IconName':str(Path(__file__).with_name('app-icon.png')),'ItemIsMenu':False,'Menu':'/Menu'}
  if name not in values:return None
  return GLib.Variant('b' if name=='ItemIsMenu' else 'o' if name=='Menu' else 's',values[name])
 def show(self):self.window.show();self.window.present()
 def method(self,_conn,_sender,_path,_interface,name,_parameters,invocation):
  if name in ('Activate','SecondaryActivate'):
   if self.window.get_visible():self.window.hide()
   else:self.show()
  invocation.return_value(None)
 def menu_property(self,_conn,_sender,_path,_interface,name):
  values={'Version':GLib.Variant('u',3),'TextDirection':GLib.Variant('s','ltr'),'Status':GLib.Variant('s','normal'),'IconThemePath':GLib.Variant('as',[])}
  return values.get(name)
 def menu_method(self,_conn,_sender,_path,_interface,name,parameters,invocation):
  if name=='GetLayout':
   children=[GLib.Variant('(ia{sv}av)',(1,{'label':GLib.Variant('s','Abrir Personal To-Do'),'enabled':GLib.Variant('b',True)},[])),GLib.Variant('(ia{sv}av)',(2,{'label':GLib.Variant('s','Sair'),'enabled':GLib.Variant('b',True)},[]))]
   invocation.return_value(GLib.Variant('(u(ia{sv}av))',(1,(0,{'children-display':GLib.Variant('s','submenu')},children))))
  elif name=='GetGroupProperties':
   invocation.return_value(GLib.Variant('(a(ia{sv}))',([(1,{'label':GLib.Variant('s','Abrir Personal To-Do')}),(2,{'label':GLib.Variant('s','Sair')})],)))
  elif name=='AboutToShow':invocation.return_value(GLib.Variant('(b)',(False,)))
  elif name=='Event':
   item,event,_,_=parameters.unpack();invocation.return_value(None)
   if event=='clicked':
    if item==1:self.show()
    elif item==2:GLib.idle_add(self.window.quit_app)
  else:invocation.return_value(None)
 def close(self):
  if self.connection:
   if self.menu_reg:self.connection.unregister_object(self.menu_reg)
   if self.reg:self.connection.unregister_object(self.reg)
  self.ready=False
