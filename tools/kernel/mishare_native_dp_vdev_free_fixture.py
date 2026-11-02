#!/usr/bin/env python3
"""Actions-only native DP VDEV final unref/free into production completion."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
import mishare_native_psoc_free_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
DP='qca-wifi-host-cmn/dp/wifi3.0/dp_main.c'
TYPES='qca-wifi-host-cmn/dp/wifi3.0/dp_types.h'
MODES='qca-wifi-host-cmn/dp/inc/cdp_txrx_cmn_struct.h'
NAME='dp_vdev_unref_delete'
SUPPORT=r'''
NATIVE_ENUMS
struct cdp_vdev;
typedef void (*ol_txrx_vdev_delete_cb)(void *);
typedef void (*ol_txrx_vdev_del_notify_cb)(void *,struct cdp_vdev *);
struct dp_pdev {int live;};
struct dp_vdev {
 uint8_t vdev_id;struct dp_pdev *pdev;int mod_refs[DP_MOD_ID_MAX],ref_cnt;
 struct {bool pending;ol_txrx_vdev_delete_cb callback;void *context;} delete;
 ol_txrx_vdev_del_notify_cb vdev_del_notify;void *osif_vdev;
 struct {uint8_t raw[6];} mac_addr;enum wlan_op_mode opmode;
 int peer_list_lock;struct dp_vdev *inactive_list_elem;
};
struct dp_soc {int inactive_vdev_list_lock;struct dp_vdev *inactive_vdev_list;void *ctrl_psoc;};
static struct dp_soc d96_soc;
static struct dp_pdev d96_pdev;
static struct dp_vdev *d96_vdev;
static bool d96_enabled,d96_notify_enabled,d96_unlisted;
static unsigned d96_extra,d96_step,d96_frees,d96_callbacks,d96_notifies;
static void (*d96_callback)(void *);static void *d96_context;
static int d96_dec(int *p) {assert(*p>0);return --*p;}
static bool d96_zero(int *p) {return !d96_dec(p);}
static void d96_lock(int *p) {assert(p==&d96_soc.inactive_vdev_list_lock && !*p);*p=1;}
static void d96_unlock(int *p) {assert(p==&d96_soc.inactive_vdev_list_lock && *p==1);*p=0;}
static void d96_pool(struct dp_pdev *p,unsigned id,unsigned type,unsigned flow) {
 assert(p==&d96_pdev && p->live && id==7 && type==1 && flow==7 && !d96_step);d96_step=1;
}
static void d96_tx(struct dp_vdev *v) {assert(v==d96_vdev && d96_step==1 && "EXPECTED_DP_POOL_BEFORE_TX");d96_step=2;}
static void d96_monitor_detach(struct dp_vdev *v) {assert(v==d96_vdev && d96_step==2);d96_step=3;}
static void d96_monitor_delete(struct dp_soc *s,struct dp_vdev *v) {(void)s;(void)v;assert(!"unselected monitor route");}
static void d96_lock_destroy(int *p) {assert(p==&d96_vdev->peer_list_lock && *p==1 && d96_step==3);*p=0;d96_step=4;}
static void d96_delay(struct dp_vdev *v) {assert(v==d96_vdev && d96_step==4);d96_step=5;}
static void d96_qos(struct dp_vdev *v) {assert(v==d96_vdev && d96_step==5);d96_step=6;}
static void d96_remove(struct dp_vdev **head,struct dp_vdev *v) {assert(d96_soc.inactive_vdev_list_lock==1 && *head==v && !v->inactive_list_elem);*head=NULL;}
static void d96_event(struct dp_soc *s,int event,struct dp_vdev *v) {
 assert(s==&d96_soc && event==1 && v==d96_vdev && !s->inactive_vdev_list_lock && !s->inactive_vdev_list && "EXPECTED_DP_INACTIVE_UNLINK");
 assert(d96_step==6 && "EXPECTED_DP_CLEANUP_BEFORE_EVENT");d96_step=7;
}
static void d96_dump(void *v,size_t size,void *psoc,int type,const char *name) {
 assert(v==d96_vdev && size==sizeof(*d96_vdev) && psoc==d96_soc.ctrl_psoc && type==1 && !strcmp(name,"dp_vdev") && d96_step==7);d96_step=8;
}
static void d96_notify(void *ctx,struct cdp_vdev *v) {
 assert(ctx==&d96_soc && (void*)v==d96_vdev && dp_objects==1 && d96_step==8 && !d96_notifies && "EXPECTED_DP_NOTIFY_BEFORE_STORAGE_FREE");d96_notifies++;
}
static void d96_free(struct dp_vdev *v) {
 assert(v==d96_vdev && dp_objects==1 && d96_step==8 && !d96_frees && !v->ref_cnt && "EXPECTED_DP_FINAL_REF_BEFORE_FREE");
 for(unsigned i=0;i<DP_MOD_ID_MAX;i++)assert(!v->mod_refs[i] && "EXPECTED_DP_ALL_MODULE_REFS_GONE");
 assert(d96_notifies==(unsigned)d96_notify_enabled && "EXPECTED_DP_NOTIFY_BEFORE_STORAGE_FREE");
 d96_vdev=NULL;dp_objects--;d96_frees++;d96_step=9;free(v);
}
static void d96_completed(void *context) {
 assert(!d96_vdev && !dp_objects && d96_frees==1 && d96_step==9 && "EXPECTED_DP_STORAGE_FREE_BEFORE_COMPLETION");
 assert(context==d96_context && pending_dp_ctx==context && pending_dp_cb==d96_callback && d96_callback && !d96_callbacks && "EXPECTED_DP_ORIGINAL_CALLBACK_TOKEN");
 void (*cb)(void*)=d96_callback;pending_dp_cb=NULL;pending_dp_ctx=NULL;d96_callbacks++;cb(context);
}
DP_MACROS
NATIVE_FINALIZER
DP_UNMACROS
static void d96_attach(void *soc,struct cdp_vdev_info *info) {
 assert(!d96_vdev && !d96_frees && soc && info->op_mode==wlan_op_mode_passthru);
 d96_vdev=calloc(1,sizeof(*d96_vdev));assert(d96_vdev);d96_pdev.live=1;d96_soc.ctrl_psoc=soc;
 struct dp_vdev *v=d96_vdev;v->vdev_id=info->vdev_id;v->pdev=&d96_pdev;v->opmode=info->op_mode;v->peer_list_lock=1;
 v->ref_cnt=2+d96_extra;v->mod_refs[DP_MOD_ID_CONFIG]=1;v->mod_refs[DP_MOD_ID_CHILD]=1;v->mod_refs[DP_MOD_ID_HTT]=d96_extra;
}
static void d96_detach(void (*cb)(void*),void *context) {
 struct dp_vdev *v=d96_vdev;assert(v && cb && context && !v->delete.pending);
 d96_callback=cb;d96_context=context;v->delete.pending=true;v->delete.callback=d96_completed;v->delete.context=context;
 if(d96_notify_enabled){v->vdev_del_notify=d96_notify;v->osif_vdev=&d96_soc;}
 if(!d96_unlisted)d96_soc.inactive_vdev_list=v;
 dp_vdev_unref_delete(&d96_soc,v,DP_MOD_ID_CONFIG);
 assert(d96_vdev==v && v->ref_cnt==(int)(1+d96_extra) && !d96_frees && !d96_callbacks && !d96_step && "EXPECTED_DP_NONFINAL_REF_RETAINS_STORAGE");
}
static void d96_finish(void) {
 struct dp_vdev *v=d96_vdev;assert(v && pending_dp_cb);
 for(unsigned i=0;i<d96_extra;i++) {
  dp_vdev_unref_delete(&d96_soc,v,DP_MOD_ID_HTT);
  assert(d96_vdev==v && !d96_frees && !d96_callbacks && !d96_step && "EXPECTED_DP_NONFINAL_REF_RETAINS_STORAGE");
 }
 dp_vdev_unref_delete(&d96_soc,v,DP_MOD_ID_CHILD);
 assert(!d96_vdev && d96_frees==1 && d96_callbacks==1 && !pending_dp_cb && !pending_dp_ctx && "EXPECTED_DP_FINAL_COMPLETION");
}
static void d96_check(bool retained) {
 if(retained)assert(d96_vdev && dp_objects==1 && !d96_frees && !d96_callbacks && "EXPECTED_DP_PEER_GATE_RETAINS_STORAGE");
 else assert(!d96_vdev && !dp_objects && d96_frees==1 && d96_callbacks==1 && "EXPECTED_DP_FINAL_COMPLETION");
}
'''
# Scope every platform macro around the byte-identical native function.
MACROS={
 'QDF_ASSERT':'assert','qdf_atomic_dec_return':'d96_dec','qdf_atomic_dec_and_test':'d96_zero',
 'dp_info':'ref_log','dp_tx_flow_pool_unmap_handler':'d96_pool','dp_tx_vdev_detach':'d96_tx',
 'dp_monitor_vdev_detach':'d96_monitor_detach','dp_monitor_vdev_delete':'d96_monitor_delete',
 'qdf_spinlock_destroy':'d96_lock_destroy','dp_ul_delay_lock_destroy':'d96_delay',
 'dp_vdev_free_qos_latency_mem':'d96_qos','qdf_spin_lock_bh':'d96_lock','qdf_spin_unlock_bh':'d96_unlock',
 'dp_cfg_event_record_vdev_evt':'d96_event','wlan_minidump_remove':'d96_dump','qdf_mem_common_free':'d96_free',
 'FLOW_TYPE_VDEV':'1','DP_CFG_EVENT_VDEV_UNREF_DEL':'1','WLAN_MD_DP_VDEV':'1',
 'QDF_MAC_ADDR_FMT':'"%p"','QDF_MAC_ADDR_REF(p)':'((void *)(p))',
 'TAILQ_FOREACH(v,h,f)':'for ((v)=*(h);(v);(v)=(v)->f)',
 'TAILQ_REMOVE(h,v,f)':'d96_remove(h,v)',
}

def fixture(root):
 s,exits,stubbed=previous.fixture(root)
 enums='\n'.join(re.search(r'enum '+name+r' \{.*?^\};',(root/path).read_text(),re.S|re.M)[0] for name,path in [('dp_mod_id',TYPES),('wlan_op_mode',MODES)])
 start=[];end=[]
 for key,value in MACROS.items():
  name=key.split('(')[0];start.extend([f'#pragma push_macro("{name}")',f'#undef {name}',f'#define {key} {value}']);end[0:0]=[f'#undef {name}',f'#pragma pop_macro("{name}")']
 block=SUPPORT.replace('\nNATIVE_ENUMS\n','\n'+enums+'\n').replace('\nDP_MACROS\n','\n'+'\n'.join(start)+'\n').replace('\nNATIVE_FINALIZER\n','\n'+extract((root/DP).read_text(),NAME)+'\n').replace('\nDP_UNMACROS\n','\n'+'\n'.join(end)+'\n')
 anchor='static void (*pending_dp_cb)(void *);static void *pending_dp_ctx;'
 s=owner.replace_once(s,anchor,anchor+'\n'+block)
 s=owner.replace_once(s,'dp_attaches++;dp_objects++;return dp_status;', 'dp_attaches++;dp_objects++;if(d96_enabled)d96_attach(soc,i);return dp_status;')
 s=owner.replace_once(s,'assert(pending_dp_cb && dp_objects==1);dp_objects--;','if(d96_enabled){d96_finish();return;}\n assert(pending_dp_cb && dp_objects==1);dp_objects--;')
 s=owner.replace_once(s,'pending_dp_cb=cb;pending_dp_ctx=c;if(early_dp)', 'pending_dp_cb=cb;pending_dp_ctx=c;if(d96_enabled)d96_detach(cb,c);if(early_dp)')
 case=function(s,'p92_case');updated=owner.replace_once(case,'p92_enabled=true;','d96_enabled=true;p92_enabled=true;');updated=owner.replace_once(updated,'p95_completed();','p95_completed();d96_check(peer_mode>=2 && peer_mode<=5);');s=owner.replace_once(s,case,updated)
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned notify=0;notify<2;notify++)for(unsigned unlisted=0;unlisted<2;unlisted++)for(unsigned refs=1;refs<=2;refs++) {
  pid_t c=fork();assert(c>=0);if(!c){d96_notify_enabled=notify;d96_unlisted=unlisted;d96_extra=refs;p92_case(trace,1,0,false);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==104);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==88);','assert(count==88);\n'+extra))
 assert s.count(extract((root/DP).read_text(),NAME))==1
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[
 ('nonfinal','if (!qdf_atomic_dec_and_test(&vdev->ref_cnt))','if (false && !qdf_atomic_dec_and_test(&vdev->ref_cnt))','EXPECTED_DP_FINAL_REF_BEFORE_FREE'),
 ('pool','dp_tx_flow_pool_unmap_handler(pdev, vdev_id,\n\t\t\tFLOW_TYPE_VDEV, vdev_id);','(void)pdev;(void)vdev_id;','EXPECTED_DP_POOL_BEFORE_TX'),
 ('qos','dp_vdev_free_qos_latency_mem(vdev);','/* omit qos cleanup */','EXPECTED_DP_CLEANUP_BEFORE_EVENT'),
 ('unlink','if (found)','if (false && found)','EXPECTED_DP_INACTIVE_UNLINK'),
 ('notify','vdev_del_notify(vdev_del_noitfy_ctx, (struct cdp_vdev *)vdev);','(void)vdev_del_noitfy_ctx;','EXPECTED_DP_NOTIFY_BEFORE_STORAGE_FREE'),
 ('free','qdf_mem_common_free(vdev);','/* omit free */','EXPECTED_DP_STORAGE_FREE_BEFORE_COMPLETION'),
 ('callback','vdev_delete_cb(vdev_delete_context);','(void)vdev_delete_context;','EXPECTED_DP_FINAL_COMPLETION'),
 ('context','vdev_delete_cb(vdev_delete_context);','vdev_delete_cb(NULL);(void)vdev_delete_context;','EXPECTED_DP_ORIGINAL_CALLBACK_TOKEN'),
 ]
 for label,needle,mutation,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {d96_notify_enabled=true;p92_case(false,1,0,false);_Exit(0);}')
  body=extract(target,NAME);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_DP_VDEV_FREE_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_DP_function_sha256']={NAME:hashlib.sha256(extract((root/DP).read_text(),NAME).encode()).hexdigest()}
 r['native_DP_source_sha256']=hashlib.sha256((root/DP).read_bytes()).hexdigest()
 r['native_DP_enum_source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in (TYPES,MODES)}
 r['additional_composite_cases']=104;r['negative_controls_rejected']=34
 r['checks']=['88 previous PSOC/PDEV/peer cases use native DP VDEV final unref; 16 extra combinations cover trace refs, optional pre-free notification, inactive-list absence and extra HTT refs','native original module ref decrement, final-ref gate, passthru cleanup, inactive unlink, notification, actual host heap free, then saved callback execute','completion trampoline checks actual heap release and forwards original opaque token to existing production runtime callback; pending callback fields are cleared before production callback','modeled peer cleanup failure retains DP storage and completion; no native DP peer-unmap/ObjMgr reference bridge is claimed','26 inherited and 8 new mutation controls rejected']
 r['limitations']='Native DP finalizer only. DP allocation, attach/detach admission and callback registration, initial CONFIG/CHILD/HTT ref acquisition, peer-gone gate and late HTT release are fixture models. DP cleanup endpoints, list/lock/atomic implementations and optional notification are modeled; no native DP peer unmap/ref-delete, real datapath component cleanup, firmware, asynchronous producer or kernel concurrency. Callback trampoline invokes the existing production runtime completion after actual host heap free, not kernel allocator free. Inherited PSOC/PDEV/ObjMgr constructors, component registries and shutdown coordinator remain modeled or absent. PASSTHRU selected; monitor route excluded. No production backend activation or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
