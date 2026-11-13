#!/usr/bin/env python3
"""Opaque live-registry snapshot admission, failure output and lifecycle composition."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import mishare_factory_native_lifecycle_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
EARLY=r'''
static unsigned snapshot_cut;
static struct mishare_runtime_owner *snapshot_cut_owner;
static int snapshot_radio_boundary(struct mishare_radio *,struct mishare_radio_status *);
'''
PROBES=r'''
/* A synchronous model cut only: storage/parents remain alive, and no native
 * cleanup occurs in this hook. This tests the second registry read, not a
 * claim that arbitrary concurrent teardown is supported. */
static int snapshot_radio_boundary(struct mishare_radio *r,struct mishare_radio_status *s) {
 int ret=mishare_radio_snapshot(r,s);
 unsigned cut=snapshot_cut;snapshot_cut=0;
 if(ret || !cut)return ret;
 assert(snapshot_cut_owner && !lock_depth);
 unsigned long flags;spin_lock_irqsave(&mishare_runtime_lock,flags);
 if(cut==1)snapshot_cut_owner->radio=NULL;
 if(cut==2) {
  assert(mishare_runtime_owners==snapshot_cut_owner && !snapshot_cut_owner->next);
  mishare_runtime_owners=NULL;
 }
 spin_unlock_irqrestore(&mishare_runtime_lock,flags);
 return cut==3?-EIO:0;
}
static void snapshot_probe(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status out;
 unsigned char before[sizeof(out)];
 struct mishare_radio_status rs;
 unsigned char rb[sizeof(rs)];
 struct mishare_radio *r=o->radio;
 assert(r && mishare_runtime_owners==o && !o->next);
 memset(&out,0xa5,sizeof(out));memcpy(before,&out,sizeof(out));
 assert(mishare_runtime_snapshot(NULL,&out)==-EINVAL && !memcmp(before,&out,sizeof(out)) &&
  mishare_runtime_snapshot(o,NULL)==-EINVAL && "EXPECTED_SNAPSHOT_ARGUMENTS");
 for(unsigned n=0;n<3;n++) {
  void *token=(void*)(uintptr_t)(n==0?1:n==1?0x1000:0xdeadbeef);
  assert(mishare_runtime_snapshot(token,&out)==-ENOENT && !memcmp(before,&out,sizeof(out)) &&
   "EXPECTED_SNAPSHOT_RUNTIME_OPAQUE");
 }
 memset(&rs,0x5a,sizeof(rs));memcpy(rb,&rs,sizeof(rs));
 assert(mishare_radio_snapshot(NULL,&rs)==-EINVAL && !memcmp(rb,&rs,sizeof(rs)) &&
  mishare_radio_snapshot(r,NULL)==-EINVAL && "EXPECTED_SNAPSHOT_RADIO_ARGUMENTS");
 assert(mishare_radio_snapshot((void*)1,&rs)==-ENOENT && !memcmp(rb,&rs,sizeof(rs)) &&
  "EXPECTED_SNAPSHOT_RADIO_OPAQUE");
 assert(!mishare_runtime_snapshot(o,&out) && !mishare_radio_snapshot(r,&rs) &&
  out.allocated && out.ndi.radio_requested && out.radio.phase==MISHARE_RADIO_DOWN &&
  out.radio.phase==rs.phase && out.radio.start_attempted && out.radio.stop_attempted &&
  out.radio.down_accepted && "EXPECTED_SNAPSHOT_LIVE_COMPONENT");
 /* Synthetic corrupt component handle; the actual controller is retained. */
 o->radio=(void*)1;memset(&out,0xa5,sizeof(out));memcpy(before,&out,sizeof(out));
 assert(mishare_runtime_snapshot(o,&out)==-ENOENT && !memcmp(before,&out,sizeof(out)) &&
  "EXPECTED_SNAPSHOT_COMPONENT_FAILURE");o->radio=r;
 for(unsigned cut=1;cut<=3;cut++) {
  memset(&out,0xa5,sizeof(out));memcpy(before,&out,sizeof(out));
  snapshot_cut_owner=o;snapshot_cut=cut;
  int ret=mishare_runtime_snapshot(o,&out);
  assert(ret==(cut==1?-EUCLEAN:cut==2?-ENOENT:-EIO) && !memcmp(before,&out,sizeof(out)) &&
   "EXPECTED_SNAPSHOT_SECOND_OBSERVATION");
  /* Restore only the deliberate reader cut; no release or hidden reset API. */
  if(cut==1)o->radio=r;
  if(cut==2)mishare_runtime_owners=o;
 }
 snapshot_cut_owner=NULL;
 /* No live component uses the saved scalar record, without native reads. */
 o->radio=NULL;assert(!mishare_runtime_snapshot(o,&out) && out.allocated &&
  out.ndi.radio_requested && "EXPECTED_SNAPSHOT_SCALAR_ONLY");o->radio=r;
 assert(!mishare_runtime_snapshot(o,&out) && out.radio.phase==MISHARE_RADIO_DOWN &&
  "EXPECTED_SNAPSHOT_RETAINED_CONTROLLER");
}
static void snapshot_retired(void *owner,struct mishare_radio *radio) {
 struct mishare_runtime_status s;unsigned char before[sizeof(s)];
 struct mishare_radio_status r;unsigned char rb[sizeof(r)];
 memset(&s,0xa5,sizeof(s));memcpy(before,&s,sizeof(s));
 memset(&r,0x5a,sizeof(r));memcpy(rb,&r,sizeof(r));
 assert(mishare_runtime_snapshot(owner,&s)==-ENOENT && !memcmp(before,&s,sizeof(s)) &&
  "EXPECTED_SNAPSHOT_RETIRED_RUNTIME");
 assert(mishare_radio_snapshot(radio,&r)==-ENOENT && !memcmp(rb,&r,sizeof(r)) &&
  "EXPECTED_SNAPSHOT_RETIRED_RADIO");
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    needle='#include "wlan_hdd_mishare_runtime.c"'
    assert source.count(needle)==1
    source=source.replace(needle,EARLY+'\n#define mishare_radio_snapshot snapshot_radio_boundary\n'+needle+'\n#undef mishare_radio_snapshot\n',1)
    pos=source.index('static void ordinary_case(')
    source=source[:pos]+PROBES+source[pos:]
    body=function(source,'ordinary_case')
    needle=' struct mishare_runtime_owner *o=ordinary_ready(freq,initial,early,early);'
    assert body.count(needle)==1
    changed=body.replace(needle,needle+'''
 void *snapshot_owner_token=o;struct mishare_radio *snapshot_radio_token=o->radio;
 if(freq==2437 && !initial && !early && !modes && !fault)snapshot_probe(o);
''',1)
    needle=' assert(!o && composite_closed'
    assert changed.count(needle)==1
    changed=changed.replace(needle,' snapshot_retired(snapshot_owner_token,snapshot_radio_token);\n'+needle,1)
    source=source.replace(body,changed,1)
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    radio=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_radio.c').read_text()
    body=function(runtime,'mishare_runtime_snapshot');rb=function(radio,'mishare_radio_snapshot')
    controls=[]
    # False success is itself dangerous for a readiness caller even when no
    # invalid pointer is dereferenced by this deliberately bounded mutation.
    controls.append(('wlan_hdd_mishare_runtime.c',runtime.replace(body,body.replace('return -ENOENT;','return 0;',1),1),'EXPECTED_SNAPSHOT_RUNTIME_OPAQUE'))
    controls.append(('wlan_hdd_mishare_radio.c',radio.replace(rb,rb.replace('int ret = -ENOENT;','int ret = 0;',1),1),'EXPECTED_SNAPSHOT_RADIO_OPAQUE'))
    controls.append(('wlan_hdd_mishare_runtime.c',runtime.replace(body,body.replace('entry->radio != radio','false',1),1),'EXPECTED_SNAPSHOT_SECOND_OBSERVATION'))
    needle='    for (entry = mishare_runtime_owners; entry && entry != owner; entry = entry->next)\n        ;'
    assert body.count(needle)==2
    a=body.rindex(needle);changed=body[:a]+'    entry = owner;'+body[a+len(needle):]
    controls.append(('wlan_hdd_mishare_runtime.c',runtime.replace(body,changed,1),'EXPECTED_SNAPSHOT_SECOND_OBSERVATION'))
    needle='    ret = mishare_radio_snapshot(radio, &observed);'
    assert body.count(needle)==1
    controls.append(('wlan_hdd_mishare_runtime.c',runtime.replace(body,body.replace(needle,'    *status = owner->state;\n'+needle,1),1),'EXPECTED_SNAPSHOT_COMPONENT_FAILURE'))
    for path,changed,marker in controls:
        target=directory/path
        try:
            target.write_text(changed);c_file.write_text(source);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and marker in bad.stderr,(path,marker,bad.returncode,bad.stderr[-1800:])
        finally:target.unlink(missing_ok=True)

def audit(root):
    r=previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_SNAPSHOT_OPAQUE_OWNER_LIFECYCLE_PASS_ONLY',ordinary_combinations=256,
      constructor_faults=14,reader_mutations=5,
      limitations='Actual production runtime/radio registry readers run through real factory/native constructor/ordinary close composition. A named wrapper invokes the actual radio reader then makes synchronous component/owner cuts while storage/parents remain retained, solely to test reauthentication and untouched outputs. No reference is added, no arbitrary concurrent teardown/ABA claim, no configured START/public init or phone/RF/Apple certification; existing physical primitive models remain.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
