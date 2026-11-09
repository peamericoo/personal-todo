"""Ícone de bandeja StatusNotifierItem para ambientes Linux compatíveis."""
from pathlib import Path
from gi.repository import Gio, GLib

XML='''<node><interface name="org.kde.StatusNotifierItem">
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
<property name="IconName" type="s" access="read"/><property name="ItemIsMenu" type="b" access="read"/>
<signal name="NewIcon"/><signal name="NewStatus"><arg type="s"/></signal>
</interface></node>'''
class Tray:
 def __init__(self,window):
  self.window=window;self.ready=False;self.connection=None;self.reg=None
  try:
   self.connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
   host=self.connection.call_sync('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.kde.StatusNotifierWatcher','IsStatusNotifierHostRegistered')),None,Gio.DBusCallFlags.NONE,1000,None)
   if not host.unpack()[0]: return
   info=Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
   self.reg=self.connection.register_object('/StatusNotifierItem',info,self.method,self.get_property,None)
   self.connection.call_sync('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.kde.StatusNotifierWatcher','RegisterStatusNotifierItem',GLib.Variant('(s)',(self.connection.get_unique_name(),)),None,Gio.DBusCallFlags.NONE,1000,None)
   self.ready=True
  except Exception as e: print('Bandeja indisponível:',type(e).__name__)
 def get_property(self,_conn,_sender,_path,_interface,name):
  values={'Category':'ApplicationStatus','Id':'personal-todo','Title':'Personal To-Do','Status':'Active','IconName':str(Path(__file__).with_name('app-icon.png')),'ItemIsMenu':False}
  if name not in values:return None
  return GLib.Variant('b' if name=='ItemIsMenu' else 's',values[name])
 def method(self,_conn,_sender,_path,_interface,name,_parameters,invocation):
  if name in ('Activate','SecondaryActivate','ContextMenu'):
   if self.window.get_visible(): self.window.hide()
   else: self.window.show();self.window.present()
  invocation.return_value(None)
 def close(self):
  if self.connection and self.reg:self.connection.unregister_object(self.reg)
  self.ready=False
