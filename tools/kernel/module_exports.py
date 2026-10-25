#!/usr/bin/env python3
"""exported symbol -> CRC from an AArch64 .ko (CONFIG_MODVERSIONS).

__ksymtab entries are {int value_off; int name_off; int ns_off;} (PREL32, left
unapplied in a .ko). The name field's relocation points into __ksymtab_strings
with an addend that is the string offset -- the symbol name is NOT the symbol
of the relocation.
"""
import struct, sys, json

def load(path):
    with open(path, 'rb') as source:
        d = source.read()
    e_shoff, = struct.unpack_from('<Q', d, 0x28)
    ent, num, shstr = struct.unpack_from('<HHH', d, 0x3a)
    o, s = struct.unpack_from('<QQ', d, e_shoff + shstr*ent + 0x18)
    st = d[o:o+s]
    secs = []
    for i in range(num):
        p = e_shoff + i*ent
        nm, typ = struct.unpack_from('<II', d, p)
        foff, fsz = struct.unpack_from('<QQ', d, p + 0x18)
        link, info = struct.unpack_from('<II', d, p + 0x28)
        secs.append(dict(idx=i, name=st[nm:st.index(b'\0', nm)].decode(),
                         type=typ, off=foff, size=fsz, link=link, info=info))
    return d, secs

def export_records(path, require_namespace=True):
    """Read actual export CRC, license category and namespace from a module.

    Strict mode refuses missing relocation metadata. These are exports, not
    imported expectations, and can therefore describe real symvers providers.
    """
    d, secs = load(path)
    # symbol table
    ss = next(s for s in secs if s['type'] == 2)
    t = secs[ss['link']]
    nmtab = d[t['off']:t['off']+t['size']]
    syms = []
    for i in range(ss['size'] // 24):
        p = ss['off'] + i*24
        st_name, st_info, st_other, st_shndx, value, _ = struct.unpack_from('<IBBHQQ', d, p)
        syms.append((nmtab[st_name:nmtab.index(b'\0', st_name)].decode('utf-8','replace'), st_shndx, value))

    def relocated_string(reference):
        symidx, addend = reference
        _, shndx, value = syms[symidx]
        sec = secs[shndx]
        relative = value + addend
        if not 0 <= relative < sec['size']:
            raise ValueError('Export string relocation outside its section')
        base = sec['off'] + relative
        end = d.index(b'\0', base, sec['off'] + sec['size'])
        return d[base:end].decode('utf-8')
    res = {}
    for ktab, ctab in (("__ksymtab", "__kcrctab"), ("__ksymtab_gpl", "__kcrctab_gpl")):
        k = next((s for s in secs if s['name'] == ktab), None)
        c = next((s for s in secs if s['name'] == ctab), None)
        if not k or not c:
            continue
        if k['size'] % 12 or c['size'] != k['size'] // 12 * 4:
            raise ValueError('Inconsistent export/CRC section sizes')
        rel = {}
        for r in secs:
            # sh_info identifies the target section. Android 6.12 also uses
            # combined .rela__ksymtab sections without a per-symbol suffix.
            if r['type'] == 4 and r['info'] == k['idx']:
                for i in range(r['size'] // 24):
                    p = r['off'] + i*24
                    ro, ri, ra = struct.unpack_from('<QQq', d, p)
                    rel[ro] = (ri >> 32, ra)
        for i in range(k['size'] // 12):
            nf = i*12 + 4
            if nf not in rel:
                if require_namespace:
                    raise ValueError('Missing export name relocation')
                continue
            name = relocated_string(rel[nf])
            if require_namespace and nf + 4 not in rel:
                raise ValueError(f'Missing namespace relocation: {name}')
            namespace = relocated_string(rel[nf + 4]) if nf + 4 in rel else ''
            crc, = struct.unpack_from('<I', d, c['off'] + i*4)
            record = {'crc': '0x%08x' % crc, 'namespace': namespace,
                      'export_type': 'EXPORT_SYMBOL_GPL' if ktab.endswith('_gpl') else 'EXPORT_SYMBOL'}
            if name in res and res[name] != record:
                raise ValueError(f'Conflicting export records: {name}')
            res[name] = record
    return res


def exports(path):
    return {name: record['crc'] for name, record in
            export_records(path, require_namespace=False).items()}

if __name__ == "__main__":
    if sys.argv[1] == "--dump":
        print(json.dumps(exports(sys.argv[2]), indent=1, sort_keys=True)); sys.exit(0)
    a, b = exports(sys.argv[1]), exports(sys.argv[2])
    print(f"{sys.argv[1].split('/')[-1]}: {len(a)} exports    {sys.argv[2].split('/')[-1]}: {len(b)} exports")
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    print(f"共同符号 CRC 不同: {len(diff)}")
    for k in diff[:8]: print("   ", k, a[k], "vs", b[k])
