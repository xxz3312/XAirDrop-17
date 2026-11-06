#!/usr/bin/env python3
"""Read-only AArch64 mapped pre-entry word comparison; never an ABI waiver."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from module_abi import inspect
from module_exports import load, export_records


def prefixes(path,names):
    inspect(path)  # Existing bounded ELF/AArch64 validation.
    data,sections=load(path)
    table=next(s for s in sections if s['type']==2);strings=sections[table['link']]
    text=data[strings['off']:strings['off']+strings['size']];symbols=[]
    if table['size']%24:raise ValueError('Malformed ELF64 symbol table')
    for offset in range(table['off'],table['off']+table['size'],24):
        nm,info,other,section,value,size=struct.unpack_from('<IBBHQQ',data,offset)
        if nm>=len(text):raise ValueError('Symbol name outside string table')
        end=text.find(b'\0',nm)
        if end<0:raise ValueError('Unterminated symbol name')
        symbols.append((text[nm:end].decode(),info,section,value))
    data_maps={(s,v) for n,i,s,v in symbols if n=='$d' or n.startswith('$d.')}
    code_maps={(s,v) for n,i,s,v in symbols if n=='$x' or n.startswith('$x.')}
    result={}
    for name,info,section,value in symbols:
        if name not in names or info&15!=2:continue
        if not 0<section<len(sections) or value<4:raise ValueError('Invalid function section/entry')
        sec=sections[section]
        if value>sec['size']:raise ValueError('Function entry outside section')
        if (section,value-4) not in data_maps or (section,value) not in code_maps:
            raise ValueError('Expected AArch64 data/code mapping at function prefix: '+name)
        prefix=struct.unpack_from('<I',data,sec['off']+value-4)[0]
        if name in result:raise ValueError('Duplicate exported function definition')
        result[name]=f'0x{prefix:08x}'
    if set(result)!=set(names):raise ValueError('Missing exported function prefixes: '+str(sorted(set(names)-set(result))))
    return result


def audit(stock,candidate,table):
    reference=next(x for x in table['modules'] if x['name']=='icnss2')
    digest=hashlib.sha256(stock.read_bytes()).hexdigest()
    if digest!=reference['sha256']:raise ValueError('Stock ICNSS file differs from recorded firmware')
    if export_records(stock)!=reference['exports']:raise ValueError('Actual stock export records differ')
    a=prefixes(stock,reference['exports']);b=prefixes(candidate,reference['exports'])
    changed={name:{'stock':a[name],'candidate':b[name]} for name in a if a[name]!=b[name]}
    return {'status':'MAPPED_PRE_ENTRY_WORDS_MATCH_ONLY' if not changed else 'MAPPED_PRE_ENTRY_WORD_DIFFERENCES',
            'stock_sha256':digest,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
            'mapped_function_count':len(a),'changed':changed,'stock':a,'candidate':b,
            'limitations':'Actual four-byte data words immediately preceding mapped AArch64 exported function entries, in the recorded KCFI-enabled builds. Does not validate other callers, transitive pointee types, CRC streams, all KCFI sites or loading; never overrides the export CRC gate.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--exports',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.stock,a.candidate,json.loads(a.exports.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['mapped_function_count'])
