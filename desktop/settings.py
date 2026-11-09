"""Configuração local opcional, sem armazenamento da chave em texto pelo cliente."""
import json, os
from pathlib import Path
from urllib.parse import urlparse

def settings():
    path=Path(os.getenv('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'personal-todo'/'connection.json'
    try:
        value=json.loads(path.read_text()); return value if isinstance(value,dict) else {}
    except (OSError,ValueError): return {}

def connection():
    config=settings(); url=os.getenv('TODO_MCP_URL') or config.get('url',''); key=os.getenv('TODO_MCP_TOKEN','').strip(); key_path=os.getenv('TODO_MCP_TOKEN_FILE') or config.get('token_file','')
    if not key and key_path:
        try:key=Path(key_path).expanduser().read_text().strip()
        except OSError:pass
    return url,key


def safe_url(url):
    p=urlparse(url)
    return bool(p.hostname) and not p.username and not p.password and (p.scheme=='https' or (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1')))
