"""Safe GTK rendering of Markdown without executing HTML or external content."""
def render(text, view):
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        return False
    buf=view.get_buffer();buf.set_text('');table=buf.get_tag_table()
    styles={'heading':{'weight':700,'scale':1.3},'strong':{'weight':700},'em':{'style':2},'code':{'family':'monospace','background':'#292c35'},'link':{'foreground':'#aebcf5','underline':1},'quote':{'foreground':'#b7c1e8','left-margin':12}}
    for name,props in styles.items():
        if not table.lookup(name):buf.create_tag(name,**props)
    active=[];lists=[];line_start=True
    def put(content):
        nonlocal line_start
        if not content:return
        if active:buf.insert_with_tags_by_name(buf.get_end_iter(),content,*dict.fromkeys(active))
        else:buf.insert(buf.get_end_iter(),content)
        line_start=content.endswith('\n')
    def newline():
        if not line_start:put('\n')
    def process(tokens):
        for token in tokens:
            t=token.type
            if t=='inline':process(token.children or [])
            elif t in ('text','html_inline'):
                value=token.content
                if value.startswith('[ ] '):value='☐ '+value[4:]
                elif value[:4].lower()=='[x] ':value='☑ '+value[4:]
                put(value)
            elif t in ('softbreak','hardbreak'):put('\n')
            elif t=='code_inline':active.append('code');put(token.content);active.pop()
            elif t in ('fence','code_block'):newline();active.append('code');put(token.content);active.pop();newline()
            elif t in ('heading_open','strong_open','em_open','link_open','blockquote_open'):
                if t in ('heading_open','blockquote_open'):newline()
                active.append({'heading_open':'heading','strong_open':'strong','em_open':'em','link_open':'link','blockquote_open':'quote'}[t])
            elif t in ('heading_close','strong_close','em_close','link_close','blockquote_close'):
                tag={'heading_close':'heading','strong_close':'strong','em_close':'em','link_close':'link','blockquote_close':'quote'}[t]
                if tag in active:active.remove(tag)
                if t in ('heading_close','blockquote_close'):newline()
            elif t in ('bullet_list_open','ordered_list_open'):lists.append([t=='ordered_list_open',int(token.attrGet('start') or 1)])
            elif t in ('bullet_list_close','ordered_list_close'):
                if lists:lists.pop()
            elif t=='list_item_open':
                newline();prefix='  '*max(0,len(lists)-1)
                if lists and lists[-1][0]:prefix+=str(lists[-1][1])+'. ';lists[-1][1]+=1
                else:prefix+='• '
                put(prefix)
            elif t in ('paragraph_close','list_item_close','hr'):newline()
            elif t=='image':put(token.content or '[imagem]')
    process(MarkdownIt('commonmark',{'html':False}).parse(text));return True
