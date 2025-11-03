# -*- coding: utf-8 -*-
import re, html

def fix_infortisa_html(s: str) -> str:
    if not s:
        return ''
    s = html.unescape(str(s)).replace('\ufeff','').strip()

    # Repara comillas duplicadas en atributos: key=""value"" -> key="value"
    def _fix_tag(m):
        tag = m.group(0)
        tag = re.sub(r'([:\w-]+)\s*=\s*""([^"]*)""', r'\1="\2"', tag)
        tag = re.sub(r'\b(width|height|valign|align|class|id)\s*=\s*""([^"]*)""', r'\1="\2"', tag, flags=re.I)
        tag = tag.replace('""','"')
        tag = re.sub(r'\s+[A-Za-z_:][-A-Za-z0-9_:.]*\s*=\s*""\s*', ' ', tag)
        tag = re.sub(r'\s{2,}', ' ', tag)
        return tag

    s = re.sub(r'(?is)<[^>]+>', _fix_tag, s)

    # Si faltan </table>, ciérralas
    open_tables  = len(re.findall(r'(?is)<table\b', s))
    close_tables = len(re.findall(r'(?is)</table>', s))
    if close_tables < open_tables:
        s += '</table>' * (open_tables - close_tables)

    return s.strip()
