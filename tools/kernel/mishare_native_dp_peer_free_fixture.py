#!/usr/bin/env python3
"""Actions-only original DP peer final free returning its VDEV CHILD lease."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_dp_vdev_free_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
DP=previous.DP
TYPES=previous.TYPES
HTT='fw-api/fw/htt_common.h'
NAME='dp_peer_unref_delete'
SUPPORT=r'''
NATIVE_PEER_ENUM
#define HTT_INVALID_PEER 0xffff
struct dp_peer {
 struct dp_vdev *vdev;uint16_t peer_id;int mod_refs[DP_MOD_ID_MAX],ref_cnt;
 struct {uint8_t raw[6];} mac_addr;
 struct dp_peer *inactive_list_elem;
 struct {unsigned count;} ast_entry_list;
 int peer_state_lock,txrx_peer_lock;enum dp_peer_state state;
};
static struct dp_peer *d97_peer;
static unsigned d97_extra,d97_step,d97_frees;
static bool d97_rx,d97_reverse,d97_unlisted;
static int d97_read(int *p) {return *p;}
static void d97_assert(bool value) {assert(value && "EXPECTED_DP_PEER_NATIVE_ADMISSION");}
static void d97_sawf(struct dp_soc *s,struct dp_peer *p) {
 assert(s==&d96_soc && p==d97_peer && !p->ref_cnt && !d97_step);d97_step=1;
}
static void d97_dump(void *p,size_t n,void *psoc,unsigned type,const char *name) {
 assert(p==d97_peer && n==sizeof(*d97_peer) && psoc==d96_soc.ctrl_psoc && type==2 && !strcmp(name,"dp_peer") && d97_step==1);d97_step=2;
}
static void d97_lock(int *p) {assert(p==&d96_soc.inactive_peer_list_lock && !*p);*p=1;}
static void d97_unlock(int *p) {assert(p==&d96_soc.inactive_peer_list_lock && *p==1);*p=0;}
static void d97_remove(struct dp_peer **head,struct dp_peer *p) {
 assert(d96_soc.inactive_peer_list_lock==1 && *head==p && !p->inactive_list_elem);*head=NULL;
}
static void d97_state(struct dp_soc *s,struct dp_peer *p,enum dp_peer_state state) {
 assert(s==&d96_soc && p==d97_peer && state==DP_PEER_STATE_FREED && d97_step==2 && !s->inactive_peer_list_lock && !s->inactive_peer_list && "EXPECTED_DP_PEER_INACTIVE_UNLINK");
 assert(!p->ast_entry_list.count && "EXPECTED_DP_PEER_EMPTY_AST");p->state=state;d97_step=3;
}
static void d97_cleanup(struct dp_vdev *v,struct dp_peer *p) {
 assert(v==d96_vdev && p==d97_peer && p->state==DP_PEER_STATE_FREED && d97_step==3 && "EXPECTED_DP_PEER_STATE_BEFORE_CLEANUP");d97_step=4;
}
static void d97_monitor(struct dp_soc *s,struct dp_peer *p) {
 assert(s==&d96_soc && p==d97_peer && d97_step==4 && "EXPECTED_DP_PEER_CLEANUP_BEFORE_MONITOR");d97_step=5;
}
static void d97_lock_destroy(int *lock) {
 assert(d97_peer);
 if(lock==&d97_peer->peer_state_lock){assert(*lock==1 && d97_step==5);*lock=0;d97_step=6;return;}
 assert(lock==&d97_peer->txrx_peer_lock && *lock==1 && d97_step==7 && "EXPECTED_DP_PEER_TXRX_DETACH_BEFORE_LOCK_FREE");*lock=0;d97_step=8;
}
static void d97_txrx(struct dp_soc *s,struct dp_peer *p) {
 assert(s==&d96_soc && p==d97_peer && !p->peer_state_lock && d97_step==6 && "EXPECTED_DP_PEER_STATE_LOCK_BEFORE_TXRX");d97_step=7;
}
static void d97_event(struct dp_soc *s,unsigned event,struct dp_peer *p,struct dp_vdev *v,unsigned flags) {
 assert(s==&d96_soc && event==2 && p==d97_peer && v==d96_vdev && !flags && !p->peer_state_lock && !p->txrx_peer_lock && d97_step==8 && "EXPECTED_DP_PEER_LOCKS_BEFORE_EVENT");d97_step=9;
}
static void d97_free(struct dp_peer *p) {
 assert(p==d97_peer && !p->ref_cnt && d97_step==9 && !d97_frees && !d96_soc.inactive_peer_list && "EXPECTED_DP_PEER_CLEANUP_BEFORE_FREE");
 assert(p->peer_id==HTT_INVALID_PEER && !p->ast_entry_list.count && "EXPECTED_DP_PEER_UNMAPPED_BEFORE_FREE");
 for(unsigned i=0;i<DP_MOD_ID_MAX;i++)assert(!p->mod_refs[i] && "EXPECTED_DP_PEER_MODULE_REFS_GONE");
 assert(d96_vdev && d96_vdev->ref_cnt==1 && d96_vdev->mod_refs[DP_MOD_ID_CHILD]==1 && !d96_step && !d96_frees && !d96_callbacks && "EXPECTED_DP_PEER_OWNS_CHILD_UNTIL_FREE");
 d97_peer=NULL;d97_frees++;d97_step=10;free(p);
}
static void d97_child_put(struct dp_soc *s,struct dp_vdev *v,enum dp_mod_id id) {
 assert(!d97_peer && d97_frees==1 && d97_step==10 && "EXPECTED_DP_PEER_FREE_BEFORE_CHILD_PUT");
 assert(s==&d96_soc && v==d96_vdev && id==DP_MOD_ID_CHILD);dp_vdev_unref_delete(s,v,id);
}
PEER_MACROS
NATIVE_PEER_FINALIZER
PEER_UNMACROS
static void d97_attach(void) {
 assert(!d97_peer && !d97_frees && d96_vdev);d96_pdev.soc=&d96_soc;
 d97_peer=calloc(1,sizeof(*d97_peer));assert(d97_peer);
 struct dp_peer *p=d97_peer;p->vdev=d96_vdev;p->peer_id=42;p->state=DP_PEER_STATE_INACTIVE;p->peer_state_lock=p->txrx_peer_lock=1;
 p->ref_cnt=2+d97_extra+d97_rx;p->mod_refs[DP_MOD_ID_CONFIG]=1;p->mod_refs[DP_MOD_ID_HTT]=1;p->mod_refs[DP_MOD_ID_TX]=d97_extra;
 /* Native RX/TX_RX/TX_COMP module IDs do not have per-module counters here. */
 if(!d97_unlisted)d96_soc.inactive_peer_list=p;
}
static void d97_retained(struct dp_peer *p) {
 assert(d97_peer==p && !d97_frees && !d97_step && d96_vdev && !d96_step && !d96_callbacks && "EXPECTED_DP_PEER_NONFINAL_RETAINS_CHILD");
}
static void d97_finish(void) {
 struct dp_peer *p=d97_peer;assert(p && p->peer_id==42 && d96_vdev && d96_vdev->ref_cnt==1);
 /* Mapping removal and these releases are fixture-selected, not firmware unmap. */
 p->peer_id=HTT_INVALID_PEER;
 enum dp_mod_id first=d97_reverse?DP_MOD_ID_HTT:DP_MOD_ID_CONFIG;
 enum dp_mod_id last=d97_reverse?DP_MOD_ID_CONFIG:DP_MOD_ID_HTT;
 dp_peer_unref_delete(p,first);d97_retained(p);
 for(unsigned i=0;i<d97_extra;i++){dp_peer_unref_delete(p,DP_MOD_ID_TX);d97_retained(p);}
 if(d97_rx){dp_peer_unref_delete(p,DP_MOD_ID_RX);d97_retained(p);}
 dp_peer_unref_delete(p,last);
 assert(!d97_peer && d97_frees==1 && d97_step==10 && "EXPECTED_DP_PEER_ACTUAL_HEAP_FREE");
}
static void d97_check(bool retained) {
 if(retained)assert(d97_peer && !d97_frees && !d97_step && "EXPECTED_DP_PEER_GATE_RETAINS_CHILD");
 else assert(!d97_peer && d97_frees==1 && d97_step==10 && "EXPECTED_DP_PEER_ACTUAL_HEAP_FREE");
}
'''
MACROS={
 'QDF_ASSERT':'d97_assert','DP_AST_ASSERT(x)':'assert((x) && "EXPECTED_DP_PEER_EMPTY_AST")',
 'qdf_atomic_dec_return':'d96_dec','qdf_atomic_dec_and_test':'d96_zero','qdf_atomic_read':'d97_read',
 'dp_peer_info':'ref_log','dp_peer_sawf_ctx_free':'d97_sawf','wlan_minidump_remove':'d97_dump',
 'qdf_spin_lock_bh':'d97_lock','qdf_spin_unlock_bh':'d97_unlock',
 'TAILQ_FOREACH(v,h,f)':'for ((v)=*(h);(v);(v)=(v)->f)','TAILQ_REMOVE(h,v,f)':'d97_remove(h,v)',
 'TAILQ_EMPTY(h)':'(!(h)->count)',
 'dp_peer_update_state':'d97_state','dp_peer_cleanup':'d97_cleanup','dp_monitor_peer_detach':'d97_monitor',
 'qdf_spinlock_destroy':'d97_lock_destroy','dp_txrx_peer_detach':'d97_txrx',
 'dp_cfg_event_record_peer_evt':'d97_event','qdf_mem_free':'d97_free','dp_vdev_unref_delete':'d97_child_put',
 'WLAN_MD_DP_PEER':'2','DP_CFG_EVENT_PEER_UNREF_DEL':'2',
 'QDF_MAC_ADDR_FMT':'"%p"','QDF_MAC_ADDR_REF(p)':'((void *)(p))',
}

def fixture(root):
 s,exits,stubbed=previous.fixture(root)
 s=owner.replace_once(s,'struct dp_pdev {int live;};','struct dp_soc;struct dp_peer;struct dp_pdev {int live;struct dp_soc *soc;};')
 s=owner.replace_once(s,'struct dp_soc {int inactive_vdev_list_lock;','struct dp_soc {int inactive_peer_list_lock;struct dp_peer *inactive_peer_list;int inactive_vdev_list_lock;')
 enums=re.search(r'enum dp_peer_state \{.*?^\};',(root/TYPES).read_text(),re.S|re.M)[0]
 assert re.search(r'^#define HTT_INVALID_PEER\s+0xffff$',(root/HTT).read_text(),re.M)
 start=[];end=[]
 for key,value in MACROS.items():
  name=key.split('(')[0];start.extend([f'#pragma push_macro("{name}")',f'#undef {name}',f'#define {key} {value}']);end[0:0]=[f'#undef {name}',f'#pragma pop_macro("{name}")']
 block=SUPPORT.replace('\nNATIVE_PEER_ENUM\n','\n'+enums+'\n').replace('\nPEER_MACROS\n','\n'+'\n'.join(start)+'\n').replace('\nNATIVE_PEER_FINALIZER\n','\n'+extract((root/DP).read_text(),NAME)+'\n').replace('\nPEER_UNMACROS\n','\n'+'\n'.join(end)+'\n')
 anchor='static void d96_attach(void *soc,struct cdp_vdev_info *info) {'
 s=owner.replace_once(s,anchor,'static void d97_attach(void);\nstatic void d97_finish(void);\n'+anchor)
 s=owner.replace_once(s,'v->mod_refs[DP_MOD_ID_HTT]=d96_extra;','v->mod_refs[DP_MOD_ID_HTT]=d96_extra;d97_attach();')
 finish=function(s,'d96_finish');s=owner.replace_once(s,finish,owner.replace_once(finish,'dp_vdev_unref_delete(&d96_soc,v,DP_MOD_ID_CHILD);','d97_finish();'))
 # Insert after native VDEV code and before later lifecycle callers.
 check=function(s,'d96_check');s=owner.replace_once(s,check,check+'\n'+block)
 case=function(s,'p92_case');s=owner.replace_once(s,case,owner.replace_once(case,'d96_check(peer_mode>=2 && peer_mode<=5);','d96_check(peer_mode>=2 && peer_mode<=5);d97_check(peer_mode>=2 && peer_mode<=5);'))
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned rx=0;rx<2;rx++)for(unsigned reverse=0;reverse<2;reverse++)for(unsigned unlisted=0;unlisted<2;unlisted++) {
  pid_t c=fork();assert(c>=0);if(!c){d97_rx=rx;d97_reverse=reverse;d97_unlisted=unlisted;d97_extra=2;d96_extra=2;d96_notify_enabled=true;p92_case(trace,1,0,false);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==120);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==104);','assert(count==104);\n'+extra))
 for n in [NAME,previous.NAME]:assert s.count(extract((root/DP).read_text(),n))==1
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[
 ('nonfinal',NAME,'if (qdf_atomic_dec_and_test(&peer->ref_cnt))','if (true || qdf_atomic_dec_and_test(&peer->ref_cnt))','!p->ref_cnt'),
 ('mapped',NAME,'QDF_ASSERT(peer_id == HTT_INVALID_PEER);','(void)peer_id;','EXPECTED_DP_PEER_UNMAPPED_BEFORE_FREE'),
 ('unlink',NAME,'if (found)','if (false && found)','EXPECTED_DP_PEER_INACTIVE_UNLINK'),
 ('ast',NAME,'DP_AST_ASSERT(TAILQ_EMPTY(&peer->ast_entry_list));','/* omit AST assertion */','EXPECTED_DP_PEER_EMPTY_AST'),
 ('state',NAME,'dp_peer_update_state(soc, peer, DP_PEER_STATE_FREED);','/* omit state */','EXPECTED_DP_PEER_STATE_BEFORE_CLEANUP'),
 ('cleanup',NAME,'dp_peer_cleanup(vdev, peer);','/* omit cleanup */','EXPECTED_DP_PEER_CLEANUP_BEFORE_MONITOR'),
 ('state_lock',NAME,'qdf_spinlock_destroy(&peer->peer_state_lock);','/* omit state lock */','EXPECTED_DP_PEER_STATE_LOCK_BEFORE_TXRX'),
 ('txrx',NAME,'dp_txrx_peer_detach(soc, peer);','/* omit txrx detach */','EXPECTED_DP_PEER_TXRX_DETACH_BEFORE_LOCK_FREE'),
 ('free',NAME,'qdf_mem_free(peer);','/* omit peer free */','EXPECTED_DP_PEER_FREE_BEFORE_CHILD_PUT'),
 ('child',NAME,'dp_vdev_unref_delete(soc, vdev, DP_MOD_ID_CHILD);','/* omit child put */','EXPECTED_DP_FINAL_COMPLETION'),
 ]
 for label,name,needle,mutation,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {p92_case(false,1,0,false);_Exit(0);}')
  if label=='mapped':target=owner.replace_once(target,'p->peer_id=HTT_INVALID_PEER;','/* retain mapped peer */')
  if label=='ast':target=owner.replace_once(target,'p->peer_id=HTT_INVALID_PEER;','p->peer_id=HTT_INVALID_PEER;p->ast_entry_list.count=1;')
  body=extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])
 # Native admission rejects mapped peers and nonempty AST before downstream free.
 for label,edit,marker in [('mapped-admission','/* retained mapping */','EXPECTED_DP_PEER_NATIVE_ADMISSION'),('ast-admission','p->peer_id=HTT_INVALID_PEER;p->ast_entry_list.count=1;','EXPECTED_DP_PEER_EMPTY_AST')]:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {p92_case(false,1,0,false);_Exit(0);}')
  c_file.write_text(owner.replace_once(target,'p->peer_id=HTT_INVALID_PEER;',edit));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_DP_PEER_FREE_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_DP_function_sha256']={n:hashlib.sha256(extract((root/DP).read_text(),n).encode()).hexdigest() for n in [NAME,previous.NAME]}
 r['native_DP_source_sha256']=hashlib.sha256((root/DP).read_bytes()).hexdigest();r['native_DP_enum_source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [TYPES,previous.MODES,HTT]}
 r['additional_composite_cases']=120;r['negative_controls_rejected']=46
 r['checks']=['104 previous sequences now use original dp_peer_unref_delete to return the VDEV CHILD reference; 16 extra cases combine RX counter bypass, reversed CONFIG/HTT order, missing inactive-list membership, tracing and extra TX/VDEV HTT references','native final-ref/map/AST admission, original peer cleanup order, modeled state/locks/list endpoints, actual peer heap free then native VDEV child release execute','existing production runtime callback receives original opaque token after both DP peer and DP VDEV host heap free','34 inherited controls, 10 peer finalizer mutations and 2 unmodified-native admission rejection controls pass']
 r['limitations']='Native peer final free and VDEV final free only. DP peer/VDEV construction, initial CONFIG/HTT/TX/RX/CHILD reference acquisition, mapping invalidation, peer-gone gate and release scheduling remain fixture models. The firmware dp_rx_peer_unmap_handler and DP peer create/delete/find-map APIs are not executed. DP peer and ObjMgr peer are distinct objects; their simulated ordering is not a verified production bridge. AST begins empty; SAWF, minidump, state, peer cleanup, monitor/txrx detach, list/lock/atomic endpoints remain models. Heap storage is actually freed on host under sanitizers, not by the kernel allocator. Inherited PSOC/PDEV components and shutdown coordinator remain modeled or absent; no real concurrency, firmware/phone/RF, active SSR, backend activation or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
