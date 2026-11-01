#!/usr/bin/env python3
"""Actions-only native VDEV reference admission, logical delete and final release."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
import mishare_native_objmgr_fixture as previous
from mishare_recovery_fixture import function
owner=previous.owner
engine=previous.engine
OBJECT=previous.OBJECT
STATE=previous.STATE
NAMES=['wlan_objmgr_vdev_get_ref','wlan_objmgr_vdev_get_ref_debug','wlan_objmgr_vdev_try_get_ref','wlan_objmgr_vdev_try_get_ref_debug','wlan_objmgr_vdev_release_ref','wlan_objmgr_vdev_release_ref_debug','wlan_objmgr_vdev_obj_delete']
PARENT_CONTROLS=['missing_native_SM_free','hidden_native_allocation_failure','missing_PAS_START_binding','hidden_native_callback_error','missing_native_BSS_channel_copy','missing_native_PAS_DP_MAC_update','missing_peer_ACK_gate','missing_DP_completion_gate','forward_component_order','missing_component_ASYNC_gate','missing_component_failure_gate','missing_MLME_SM_destroy_caller']
EARLY=r'''
#define QDF_STATUS_E_RESOURCES 103
#define WLAN_VDEV_OP 2
#define QDF_TRACE_LEVEL_DEBUG 1
#define QDF_TRACE_LEVEL_FATAL 2
#define WLAN_OBJMGR_RATELIMIT_THRESH 2
static bool ref_trace_mode,ref_expect_bug,ref_extra_enabled;
static unsigned ref_bug_count,ref_destroy_entries,ref_order;
static struct wlan_objmgr_vdev *ref_atomic_owner;
static void wlan_vdev_obj_lock(struct wlan_objmgr_vdev *);
static void wlan_vdev_obj_unlock(struct wlan_objmgr_vdev *);
static QDF_STATUS ref_last_destroy(struct wlan_objmgr_vdev *);
static void ref_arm_components(struct wlan_objmgr_vdev *);
static void ref_log(const char *fmt,...) {(void)fmt;}
static void ref_bug(int condition) {assert(!condition && ref_expect_bug && "UNEXPECTED_NATIVE_REFERENCE_BUG");ref_bug_count++;}
static int ref_atomic_read(qdf_atomic_t *p) {return p->value;}
static void ref_atomic_inc(qdf_atomic_t *p) {p->value++;if(p==&ref_atomic_owner->vdev_objmgr.ref_cnt)ref_atomic_owner->refs++;}
static void ref_atomic_dec(qdf_atomic_t *p) {p->value--;}
static bool ref_atomic_dec_and_test(qdf_atomic_t *p) {assert(p==&ref_atomic_owner->vdev_objmgr.ref_cnt);p->value--;ref_atomic_owner->refs--;return !p->value;}
static void ref_check(struct wlan_objmgr_vdev *v) {
 int sum=0;for(unsigned i=0;i<WLAN_REF_ID_MAX;i++){assert(v->vdev_objmgr.ref_id_dbg[i].value>=0 && "EXPECTED_NATIVE_REFERENCE_ACCOUNTING");sum+=v->vdev_objmgr.ref_id_dbg[i].value;}
 assert(sum==v->vdev_objmgr.ref_cnt.value && sum==v->refs && "EXPECTED_NATIVE_REFERENCE_ACCOUNTING");
}
static void wlan_objmgr_vdev_ref_trace(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id,const char *func,int line) {assert(v==ref_atomic_owner && id<WLAN_REF_ID_MAX && func && *func && line>0);v->ref_trace_gets++;}
static void wlan_objmgr_vdev_deref_trace(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id,const char *func,int line) {assert(v==ref_atomic_owner && id<WLAN_REF_ID_MAX && func && *func && line>0);v->ref_trace_puts++;}
static void wlan_objmgr_print_ref_ids(qdf_atomic_t *ids,int level) {assert(ref_atomic_owner && ids==ref_atomic_owner->vdev_objmgr.ref_id_dbg && (level==QDF_TRACE_LEVEL_DEBUG || level==QDF_TRACE_LEVEL_FATAL));}
static int qdf_get_pidx(void) {return 0;}
static void wlan_objmgr_notify_log_delete(struct wlan_objmgr_vdev *v,unsigned kind) {assert(v==ref_atomic_owner && kind==2 && v->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && !v->vdev_lock && !v->dead);v->dead=1;}
static void ref_selected_release(struct wlan_objmgr_vdev *,wlan_objmgr_ref_dbgid);
#pragma push_macro("QDF_ASSERT")
#pragma push_macro("obj_mgr_err")
#undef QDF_ASSERT
#undef obj_mgr_err
#define QDF_ASSERT(x) ref_bug(x)
#define obj_mgr_err ref_log
#define obj_mgr_debug ref_log
#define obj_mgr_alert ref_log
#define WLAN_OBJMGR_BUG(x) ref_bug(x)
#define qdf_atomic_read ref_atomic_read
#define qdf_atomic_inc ref_atomic_inc
#define qdf_atomic_dec ref_atomic_dec
#define qdf_atomic_dec_and_test ref_atomic_dec_and_test
#define wlan_objmgr_vdev_get_ref ref_native_get_ref
#define wlan_objmgr_vdev_get_ref_debug ref_native_get_ref_debug
#define wlan_objmgr_vdev_try_get_ref ref_native_try_get_ref
#define wlan_objmgr_vdev_try_get_ref_debug ref_native_try_get_ref_debug
#define wlan_objmgr_vdev_release_ref ref_native_release_ref
#define wlan_objmgr_vdev_release_ref_debug ref_native_release_ref_debug
#define wlan_objmgr_vdev_obj_destroy ref_last_destroy
NATIVE_REFERENCE_FUNCTIONS
#undef wlan_objmgr_vdev_obj_destroy
#undef wlan_objmgr_vdev_release_ref
#define wlan_objmgr_vdev_release_ref ref_selected_release
#define wlan_objmgr_vdev_obj_delete ref_native_obj_delete
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
NATIVE_LOGICAL_DELETE
#pragma GCC diagnostic pop
#undef wlan_objmgr_vdev_obj_delete
#undef wlan_objmgr_vdev_release_ref
#undef wlan_objmgr_vdev_release_ref_debug
#undef wlan_objmgr_vdev_try_get_ref_debug
#undef wlan_objmgr_vdev_try_get_ref
#undef wlan_objmgr_vdev_get_ref_debug
#undef wlan_objmgr_vdev_get_ref
#undef qdf_atomic_dec_and_test
#undef qdf_atomic_dec
#undef qdf_atomic_inc
#undef qdf_atomic_read
#undef WLAN_OBJMGR_BUG
#undef obj_mgr_alert
#undef obj_mgr_debug
#undef obj_mgr_err
#undef QDF_ASSERT
#pragma pop_macro("obj_mgr_err")
#pragma pop_macro("QDF_ASSERT")
static wlan_objmgr_ref_dbgid ref_map(int id) {
 switch(id) {case 1:return REF_NATIVE_HDD;case 2:return REF_NATIVE_OSIF;case 3:return REF_NATIVE_WMA;case 4:return REF_NATIVE_MAC;default:assert(!"INVALID_COMPACT_MODEL_REFERENCE_ID");return WLAN_OBJMGR_ID;}
}
static void ref_selected_get(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id) {ref_atomic_owner=v;if(ref_trace_mode)ref_native_get_ref_debug(v,id,"reference-model",__LINE__);else ref_native_get_ref(v,id);}
static QDF_STATUS ref_selected_try(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id) {ref_atomic_owner=v;return ref_trace_mode?ref_native_try_get_ref_debug(v,id,"reference-model",__LINE__):ref_native_try_get_ref(v,id);}
static void ref_selected_release(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id) {ref_atomic_owner=v;if(ref_trace_mode)ref_native_release_ref_debug(v,id,"reference-model",__LINE__);else ref_native_release_ref(v,id);}
static int wlan_objmgr_vdev_try_get_ref(struct wlan_objmgr_vdev *v,int id) {assert(!lock_depth);ref_calls++;if(ref_calls==fail_ref_at)return -1;int ret=ref_selected_try(v,ref_map(id));ref_check(v);return ret;}
static void wlan_objmgr_vdev_release_ref(struct wlan_objmgr_vdev *v,int id) {assert(!lock_depth && v);ref_check(v);ref_selected_release(v,ref_map(id));if(v==last_vdev)ref_check(v);}
static QDF_STATUS wlan_objmgr_vdev_obj_delete(struct wlan_objmgr_vdev *v) {
 assert(!lock_depth && v && !v->dead);delete_calls++;if(delete_fail)return QDF_STATUS_E_FAILURE;
 ref_check(v);ref_arm_components(v);int before=v->refs;ref_atomic_owner=v;QDF_STATUS ret=ref_native_obj_delete(v);
 assert(v==last_vdev && ret==QDF_STATUS_SUCCESS && v->dead && v->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && v->refs==before-1 && !v->vdev_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value && "EXPECTED_NATIVE_LOGICAL_DELETE_RELEASE");ref_check(v);return ret;
}
'''
LATE=r'''
static QDF_STATUS ref_last_destroy(struct wlan_objmgr_vdev *v) {
 assert(v==last_vdev && !v->refs && !v->vdev_objmgr.ref_cnt.value && v->dead && !v->vdev_lock && "EXPECTED_NATIVE_LAST_REFERENCE");ref_check(v);
 assert(!ref_trace_mode || v->ref_trace_gets==v->ref_trace_puts);ref_destroy_entries++;
 obj_dispatch(v);return obj_dispatch_result;
}
static void ref_add_holds(struct wlan_objmgr_vdev *v) {
 if(!ref_extra_enabled)return;
 assert(!v->dead);int ids[]={1,3,4};for(unsigned i=0;i<3;i++)assert(!wlan_objmgr_vdev_try_get_ref(v,ids[i]));ref_check(v);
}
static bool ref_finish(struct mishare_runtime_owner **o,int ret,struct wlan_objmgr_vdev *v,bool hold) {
 if(hold || ref_extra_enabled) {
  assert(v==last_vdev && ret==-EINPROGRESS && !obj_dispatch_calls && state(*o).host_delete_accepted && v->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && !v->vdev_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value);
  int before=v->refs;unsigned trace=v->ref_trace_gets;
  assert(wlan_objmgr_vdev_try_get_ref(v,1)==QDF_STATUS_E_RESOURCES && v->refs==before && v->ref_trace_gets==trace && "EXPECTED_NATIVE_REFERENCE_ADMISSION");
 }
 if(ref_extra_enabled) {
  static const unsigned orders[6][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};int ids[]={1,3,4};assert(ref_order<6);
  for(unsigned i=0;i<3;i++) {assert(!obj_dispatch_calls);wlan_objmgr_vdev_release_ref(v,ids[orders[ref_order][i]]);if(i<2 || hold)assert(v==last_vdev && v->refs>0 && !obj_dispatch_calls && "EXPECTED_NATIVE_LAST_REFERENCE");}
  ret=mishare_runtime_destroy(o);
 }
 bool success=obj_finish(o,ret,v,hold);if(success)assert(ref_destroy_entries==1);return success;
}
static void ref_contract(void) {
 struct wlan_objmgr_vdev v={0};wlan_objmgr_ref_dbgid id=REF_NATIVE_OSIF;
 ref_expect_bug=true;unsigned bugs=ref_bug_count;
 ref_selected_get(NULL,id);assert(ref_bug_count==++bugs);
 assert(ref_selected_try(NULL,id)==QDF_STATUS_E_FAILURE && ref_bug_count==++bugs);
 ref_selected_release(NULL,id);assert(ref_bug_count==++bugs);
 v.vdev_objmgr.ref_cnt.value=v.refs=2;ref_selected_release(&v,id);
 assert(ref_bug_count==++bugs && v.refs==2 && v.vdev_objmgr.ref_cnt.value==2 && !v.vdev_objmgr.ref_id_dbg[id].value && "EXPECTED_NATIVE_REFERENCE_ID_GATE");
 v.vdev_objmgr.ref_cnt.value=v.refs=0;v.vdev_objmgr.ref_id_dbg[id].value=1;ref_selected_release(&v,id);
 assert(ref_bug_count==++bugs && !v.refs && !v.vdev_objmgr.ref_cnt.value && v.vdev_objmgr.ref_id_dbg[id].value==1);
 memset(&v,0,sizeof(v));ref_expect_bug=false;v.obj_state=WLAN_OBJ_STATE_CREATED;ref_selected_get(&v,WLAN_OBJMGR_ID);ref_check(&v);
 assert(!ref_selected_try(&v,id) && v.refs==2 && v.vdev_objmgr.ref_id_dbg[id].value==1);ref_check(&v);ref_selected_release(&v,id);ref_check(&v);assert(v.refs==1);
 for(unsigned state=0;state<=WLAN_OBJ_STATE_DELETION_FAILED;state++)if(state!=WLAN_OBJ_STATE_CREATED) {
  v.obj_state=state;unsigned trace=v.ref_trace_gets;
  assert(ref_selected_try(&v,id)==QDF_STATUS_E_RESOURCES && v.refs==1 && !v.vdev_lock && v.ref_trace_gets==trace && "EXPECTED_NATIVE_REFERENCE_ADMISSION");ref_check(&v);
 }
 assert(v.vdev_objmgr.print_cnt==8);v.obj_state=WLAN_OBJ_STATE_LOGICALLY_DELETED;
 /* Unlike try_get_ref, raw get_ref has no state admission check. */
 ref_selected_get(&v,id);assert(v.refs==2);ref_selected_release(&v,id);ref_check(&v);assert(v.refs==1);
}
static void ref_extra_cases(void) {
 for(unsigned order=0;order<6;order++)for(unsigned hold=0;hold<2;hold++) {pid_t c=fork();assert(c>=0);if(!c) {ref_extra_enabled=true;ref_order=order;clean_modes=hold?8:0;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''

def ref_enum(root):
 return re.search(r'^typedef enum \{\n\s*WLAN_OBJMGR_ID.*?^\} wlan_objmgr_ref_dbgid;', (root/STATE).read_text(),re.M|re.S)[0]

def fixture(root):
 source,exits,stubbed=previous.fixture(root)
 source=owner.replace_once(source,'#define WLAN_HDD_ID_OBJ_MGR 1',ref_enum(root)+'\nstatic const wlan_objmgr_ref_dbgid REF_NATIVE_HDD=WLAN_HDD_ID_OBJ_MGR,REF_NATIVE_OSIF=WLAN_OSIF_ID,REF_NATIVE_WMA=WLAN_LEGACY_WMA_ID,REF_NATIVE_MAC=WLAN_LEGACY_MAC_ID;\n#define WLAN_HDD_ID_OBJ_MGR 1')
 source=owner.replace_once(source,'WLAN_OBJ_STATE obj_state;','WLAN_OBJ_STATE obj_state;struct {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt;uint8_t vdev_id;} vdev_objmgr;unsigned ref_trace_gets,ref_trace_puts;bool ref_components_armed;')
 old='\n'.join(re.search(r'^static [^\n]*\b'+n+r'\([^\n]*$',source,re.M)[0] for n in ['wlan_objmgr_vdev_try_get_ref','wlan_objmgr_vdev_release_ref','wlan_objmgr_vdev_obj_delete'])
 assert old in source
 text=(root/OBJECT).read_text();refs='\n'.join(function(text,n) for n in NAMES[:-1]);block=EARLY.replace('\nNATIVE_REFERENCE_FUNCTIONS\n','\n'+refs+'\n').replace('\nNATIVE_LOGICAL_DELETE\n','\n'+function(text,NAMES[-1])+'\n')
 source=owner.replace_once(source,old,block)
 source=owner.replace_once(source,'v->refs=1;memcpy(v->mac,params->macaddr,6);','v->obj_state=WLAN_OBJ_STATE_CREATED;v->vdev_objmgr.vdev_id=7;ref_selected_get(v,WLAN_OBJMGR_ID);ref_check(v);memcpy(v->mac,params->macaddr,6);')
 source=owner.replace_once(source,'if(defer_ref)v->refs++;','if(defer_ref){ref_selected_get(v,REF_NATIVE_OSIF);ref_check(v);}')
 source=owner.replace_once(source,'last_vdev->refs++;return last_vdev;','ref_selected_get(last_vdev,REF_NATIVE_HDD);ref_check(last_vdev);return last_vdev;')
 dispatch=function(source,'obj_dispatch');begin=dispatch.index(' memset(&obj_handlers');end=dispatch.index(' if(obj_mode==4)')
 setup=dispatch[begin:end]
 arm='static void ref_arm_components(struct wlan_objmgr_vdev *v) {\n assert(v==last_vdev && clean_active && v->obj_state==WLAN_OBJ_STATE_CREATED && v->refs>0 && !v->ref_components_armed);v->ref_components_armed=true;\n'+setup+'}\n'
 changed=owner.replace_once(dispatch,setup,' assert(v->ref_components_armed);\n')
 source=owner.replace_once(source,dispatch,arm+changed)
 source=owner.replace_once(source,'static void clean_end(',LATE[:LATE.index('static void ref_contract')]+ '\nstatic void clean_end(')
 clean=function(source,'clean_end');changed_clean=owner.replace_once(clean,'struct wlan_objmgr_vdev *held=last_vdev;','struct wlan_objmgr_vdev *held=last_vdev;ref_add_holds(held);');changed_clean=owner.replace_once(changed_clean,'if(!obj_finish(o,ret,held,hold))return;','if(!ref_finish(o,ret,held,hold))return;');source=owner.replace_once(source,clean,changed_clean)
 main=function(source,'main');body=owner.replace_once(main,'int main(void)','static int ref_baseline(void)');body=owner.replace_once(body,'puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");','ref_extra_cases();')
 wrapper='int main(void) {\nfor(unsigned trace=0;trace<2;trace++){pid_t c=fork();assert(c>=0);if(!c){ref_trace_mode=trace;ref_contract();assert(!ref_baseline());_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));}puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");return 0;\n}'
 extra=LATE[LATE.index('static void ref_contract'):]
 source=owner.replace_once(source,main,extra+'\n'+body+'\n'+wrapper)
 for name in NAMES:assert source.count(function(text,name))==1,name
 return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 for trace in range(2):
  suffix='_debug' if trace else ''
  controls=[('last_reference','wlan_objmgr_vdev_release_ref'+suffix,'if (qdf_atomic_dec_and_test(&vdev->vdev_objmgr.ref_cnt))','if ((qdf_atomic_dec_and_test(&vdev->vdev_objmgr.ref_cnt), true))','EXPECTED_NATIVE_LAST_REFERENCE'),('reference_id_gate','wlan_objmgr_vdev_release_ref'+suffix,'if (!qdf_atomic_read(&vdev->vdev_objmgr.ref_id_dbg[id])) {','if (false) {','EXPECTED_NATIVE_REFERENCE_ID_GATE'),('reference_accounting','wlan_objmgr_vdev_release_ref'+suffix,'qdf_atomic_dec(&vdev->vdev_objmgr.ref_id_dbg[id]);','/* negative: omit per-ID decrement */','EXPECTED_NATIVE_REFERENCE_ACCOUNTING'),('reference_admission','wlan_objmgr_vdev_try_get_ref'+suffix,'if (vdev->obj_state != WLAN_OBJ_STATE_CREATED) {','if (false) {','EXPECTED_NATIVE_REFERENCE_ADMISSION')]
  for label,name,needle,mutation,marker in controls:
   target=owner.replace_once(source,function(source,'main'),f'int main(void) {{ref_trace_mode={trace};ref_contract();_Exit(0);}}');c_file.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
   body=function(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,trace,bad.returncode,bad.stderr[-300:])
 target=owner.replace_once(source,function(source,'main'),'int main(void) {engine_cycle(5240,false,0);_Exit(0);}')
 c_file.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
 body=function(target,'wlan_objmgr_vdev_obj_delete');c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,'wlan_objmgr_vdev_release_ref(vdev, WLAN_OBJMGR_ID);','/* negative: omit object-manager owned reference release */')));subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and 'EXPECTED_NATIVE_LOGICAL_DELETE_RELEASE' in bad.stderr

def audit(root):
 report=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);report['base_engine_status']=report['status'];report['status']='MISHARE_NATIVE_REFERENCE_RELEASE_FIXTURE_PASS_ONLY'
 report['native_reference_function_sha256']={n:hashlib.sha256(function((root/OBJECT).read_text(),n).encode()).hexdigest() for n in NAMES};report['native_reference_id_enum_sha256']=hashlib.sha256(ref_enum(root).encode()).hexdigest()
 controls=PARENT_CONTROLS+[label+suffix for suffix in ['','_debug'] for label in ['last_reference','reference_id_gate','reference_accounting','reference_admission']]+['logical_delete_reference_release']
 for name in controls:report['negative_control_'+name+'_rejected']=True
 report['checks']=['seven original native VDEV reference/logical-delete functions and full original 109-ID enum; normal and debug/trace variants both execute','both variants repeat the complete 0087 main suite, inherited failure cases and component contracts','native try_get_ref rejects all eight non-CREATED states; raw native get_ref deliberately has no state admission gate','native logical delete closes admission before notification and releases the OBJMGR-owned ref; real aggregate/per-ID atomic decrements decide the sole zero-ref entry','all six permutations of three additional compact caller tags with and without a separate held reference: 12 new sequences per trace mode, 24 total','null, untracked-ID and zero-aggregate BUG contracts preserve original short-circuit behavior; counted platform traps do not certify real kernel BUG policy','compact caller tags map to native HDD/OSIF/WMA/MAC enum values; counter fields plus a checked legacy mirror replace every direct VDEV count update in this composite','all previous fifteen negatives and nine new release/admission/accounting/logical-delete mutations rejected']
 report['limitations']='Seven unchanged native get/try/release and logical-delete bodies execute, including debug variants; QDF atomics/locks, trace database callbacks, creation and handler registration remain platform models. Compact caller tags 1/2/3/4 map to native HDD/OSIF/WMA/MAC values; this is not proof of every real kernel caller tag. The legacy refs field is only a checked mirror of the native aggregate, updated by modeled atomic endpoints, never independently decremented to trigger destruction. Registered component fixtures are prepared before logical deletion; the zero-ref observation adapter invokes the original 0087 native destroy dispatcher. Native debug trace calls are modeled counters, not the real trace database. A scoped compiler diagnostic permits the native logical-delete print_idx variable that is unused in this extraction. Invalid unit states and controlled QDF_ASSERT/BUG traps are isolated contracts, not corruption recovery or kernel panic-policy certification. The original raw get_ref does not check object state; only try_get_ref provides admission. All 0087 component/CM/timer/minidump/MLO/DP-peer endpoint and serialized-concurrency limitations remain. No real DP/peer destructor graph, automatic parent coordinator, active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop certification.'
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
