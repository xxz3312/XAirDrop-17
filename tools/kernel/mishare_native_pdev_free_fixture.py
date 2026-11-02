#!/usr/bin/env python3
"""Actions-only native PDEV dispatcher/free on heap in the peer/VDEV composite."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_parent_peer_composite_fixture as previous
owner=previous.owner
engine=previous.engine
NAMES=['wlan_objmgr_pdev_object_status','wlan_objmgr_pdev_component_obj_detach','wlan_objmgr_pdev_obj_destroy','wlan_objmgr_pdev_obj_free']
SUPPORT=r'''
typedef QDF_STATUS (*wlan_objmgr_pdev_destroy_handler)(struct wlan_objmgr_pdev *,void *);
static struct {wlan_objmgr_pdev_destroy_handler pdev_destroy_handler[WLAN_UMAC_MAX_COMPONENTS];void *pdev_destroy_handler_arg[WLAN_UMAC_MAX_COMPONENTS];} p93_registry;
static unsigned p93_mode,p93_heap,p93_order,p93_free_step,p93_free_calls,p93_deinits,p93_bugs;
static void *p93_async;
static int p93_bad;
static QDF_STATUS p93_result;
static struct wlan_objmgr_pdev *p93_parent;
static QDF_STATUS p93_free_gate(struct wlan_objmgr_pdev *);
static QDF_STATUS p93_component_detach(struct wlan_objmgr_pdev *,enum wlan_umac_comp_id,void *);
static void p93_bug(int condition) {assert(!condition && p93_mode==2);p93_bugs++;}
static void p93_notify(struct wlan_objmgr_pdev *p,unsigned kind) {assert(kind==1 && p==p93_parent && p93_heap==1 && !p->p92_lock && !p->peer_obj_free_work.work.running && p92_closed && !p->pdev_objmgr.ref_cnt.value);}
static void p93_print(struct wlan_objmgr_pdev *p) {assert(p==p93_parent);}
static void p93_dump(void *p,size_t n,struct wlan_objmgr_psoc *s,unsigned kind,const char *name) {assert(p==p93_parent && n==sizeof(*p93_parent) && s==p93_parent->psoc && kind==303 && !strcmp(name,"wlan_objmgr_pdev"));}
static QDF_STATUS p93_psoc_detach(struct wlan_objmgr_psoc *s,struct wlan_objmgr_pdev *p) {
 assert(p==p93_parent && s==p->psoc && s==p->pdev_objmgr.wlan_psoc && p93_order==2 && !p93_free_step);
 if(p93_mode==3)return QDF_STATUS_E_FAILURE;
 p93_free_step=1;return QDF_STATUS_SUCCESS;
}
static void p93_lock_destroy(int *lock) {assert(p93_parent && lock==&p93_parent->pdev_lock && *lock==1 && p93_free_step==1 && "EXPECTED_PDEV_PSOC_DETACH_BEFORE_LOCK");*lock=0;p93_free_step=2;}
static QDF_STATUS p93_deinit(struct wlan_objmgr_pdev *p) {
 assert(p==p93_parent && p->q90_live && !p93_deinits && p93_free_step==2 && "EXPECTED_PDEV_LOCK_BEFORE_QUEUE");
 assert(!p->peer_obj_free_work.work.pending && !p->peer_obj_free_work.work.running && !p->peer_free_list.count && "EXPECTED_PDEV_QUEUE_IDLE_BEFORE_FREE");
 assert(!q90_native_deinit(p));p->q90_live=false;p93_deinits++;p93_free_step=3;return 0;
}
static void p93_storage_free(struct wlan_objmgr_pdev *p) {
 assert(p==p93_parent && p93_heap==1 && p93_free_step==3 && p93_deinits==1 && !p->pdev_lock && !p->peer_free_lock && !p->q90_live && "EXPECTED_PDEV_QUEUE_DEINIT_BEFORE_HEAP_FREE");
 assert(!p->peer_obj_free_work.work.running && !p->peer_obj_free_work.work.pending && !p->peer_free_list.count);
 p93_free_calls++;p93_heap--;p93_parent=NULL;free(p);
}
#define wlan_objmgr_pdev_get_pdev_id p92_id
#define wlan_pdev_obj_lock p92_lock
#define wlan_pdev_obj_unlock p92_unlock
#define wlan_objmgr_pdev_object_status p93_status
#define wlan_objmgr_pdev_component_obj_detach p93_component_detach
#define wlan_objmgr_pdev_obj_destroy p93_native_destroy
#define wlan_objmgr_pdev_obj_free p93_native_free
#define wlan_objmgr_psoc_pdev_detach p93_psoc_detach
#define wlan_delayed_peer_obj_free_deinit p93_deinit
#define qdf_spinlock_destroy p93_lock_destroy
#define qdf_mem_free p93_storage_free
#define WLAN_PDEV_OP 1
#define WLAN_MD_OBJMGR_PDEV 303
#define wlan_objmgr_notify_destroy p93_notify
#define wlan_print_pdev_info p93_print
#define wlan_minidump_remove p93_dump
#define g_umac_glb_obj (&p93_registry)
#pragma push_macro("obj_mgr_err")
#undef obj_mgr_err
#define obj_mgr_err ref_log
#define obj_mgr_debug ref_log
#define WLAN_OBJMGR_BUG(x) p93_bug(x)
#pragma push_macro("QDF_BUG")
#undef QDF_BUG
#define QDF_BUG(x) p93_bug(x)
NATIVE_FREE
#undef wlan_objmgr_pdev_obj_free
#define wlan_objmgr_pdev_obj_free p93_free_gate
NATIVE_DISPATCH
#pragma pop_macro("QDF_BUG")
#undef WLAN_OBJMGR_BUG
#undef obj_mgr_debug
#pragma pop_macro("obj_mgr_err")
#undef g_umac_glb_obj
#undef wlan_minidump_remove
#undef wlan_print_pdev_info
#undef wlan_objmgr_notify_destroy
#undef WLAN_MD_OBJMGR_PDEV
#undef WLAN_PDEV_OP
#undef qdf_mem_free
#undef qdf_spinlock_destroy
#undef wlan_delayed_peer_obj_free_deinit
#undef wlan_objmgr_psoc_pdev_detach
#undef wlan_objmgr_pdev_obj_free
#undef wlan_objmgr_pdev_obj_destroy
#undef wlan_objmgr_pdev_component_obj_detach
#undef wlan_objmgr_pdev_object_status
#undef wlan_pdev_obj_unlock
#undef wlan_pdev_obj_lock
#undef wlan_objmgr_pdev_get_pdev_id
static QDF_STATUS p93_free_gate(struct wlan_objmgr_pdev *p) {
 assert(!p93_async && "EXPECTED_PDEV_ASYNC_COMPONENT_WAIT");
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)assert(!p->pdev_comp_priv_obj[i] && p->obj_status[i]!=QDF_STATUS_E_FAILURE && "EXPECTED_PDEV_COMPONENT_SUCCESS");
 return p93_native_free(p);
}
static QDF_STATUS p93_low(struct wlan_objmgr_pdev *p,void *arg) {
 assert(arg==&p93_registry && p==p93_parent && p93_order==0 && "EXPECTED_PDEV_FORWARD_COMPONENT_ORDER");p93_order=1;
 void *token=p->pdev_comp_priv_obj[0];assert(token && !p93_component_detach(p,0,token));free(token);return QDF_STATUS_SUCCESS;
}
static QDF_STATUS p93_high(struct wlan_objmgr_pdev *p,void *arg) {
 assert(arg==&p93_registry && p==p93_parent && p93_order==1 && "EXPECTED_PDEV_FORWARD_COMPONENT_ORDER");p93_order=2;
 unsigned id=WLAN_UMAC_COMP_ID_MAX-1;void *token=p->pdev_comp_priv_obj[id];assert(token);
 if(p93_mode==2)return QDF_STATUS_E_FAILURE;
 if(p93_mode==1 || p93_mode==4){p93_async=token;p->pdev_comp_priv_obj[id]=NULL;return QDF_STATUS_COMP_ASYNC;}
 assert(!p93_component_detach(p,id,token));free(token);return QDF_STATUS_SUCCESS;
}
static void p93_arm(struct wlan_objmgr_pdev *p) {
 memset(&p93_registry,0,sizeof(p93_registry));
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)p->obj_status[i]=QDF_STATUS_COMP_DISABLED;
 unsigned ids[]={0,WLAN_UMAC_COMP_ID_MAX-1};
 for(unsigned i=0;i<2;i++){unsigned id=ids[i];p->pdev_comp_priv_obj[id]=malloc(1);assert(p->pdev_comp_priv_obj[id]);p->obj_status[id]=QDF_STATUS_SUCCESS;p93_registry.pdev_destroy_handler[id]=i?p93_high:p93_low;p93_registry.pdev_destroy_handler_arg[id]=&p93_registry;}
}
static void p93_completed(void) {
 if(p93_mode==1 || p93_mode==4){
  struct wlan_objmgr_pdev *p=p93_parent;assert(p && p93_heap==1 && p93_result==QDF_STATUS_COMP_ASYNC && p->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && p93_async && !p93_free_step && !p93_free_calls && !p93_deinits && p->q90_live);
  if(p93_mode==4){assert(p93_component_detach(p,WLAN_UMAC_COMP_ID_MAX-1,&p93_bad)==QDF_STATUS_E_FAILURE && "EXPECTED_PDEV_BAD_ASYNC_TOKEN");assert(p93_parent==p && p93_heap==1 && p93_async && p->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && !p93_free_calls && p->q90_live);return;}
  void *token=p93_async;p93_async=NULL;free(token);assert(!p93_component_detach(p,WLAN_UMAC_COMP_ID_MAX-1,NULL));
 }
 if(p93_mode==2){assert(p93_result==QDF_STATUS_E_FAILURE && p93_bugs==1 && p93_heap==1 && p93_parent && p93_parent->pdev_comp_priv_obj[WLAN_UMAC_COMP_ID_MAX-1] && !p93_free_step && !p93_deinits && p93_parent->q90_live);return;}
 if(p93_mode==3){assert(p93_result==QDF_STATUS_E_FAILURE && p93_heap==1 && p93_parent && !p93_free_step && !p93_deinits && p93_parent->pdev_lock==1 && p93_parent->q90_live);return;}
 assert(!p93_parent && !p93_heap && p93_free_calls==1 && p93_deinits==1 && p93_free_step==3 && "EXPECTED_PDEV_ACTUAL_HEAP_FREE");
}
'''

def fixture(root):
 s,exits,stubbed=previous.fixture(root);native=(root/previous.parent.PDEV).read_text()
 s=owner.replace_once(s,'struct wlan_objmgr_vdev *wlan_vdev_list;','struct wlan_objmgr_vdev *wlan_vdev_list;struct wlan_objmgr_psoc *wlan_psoc;')
 s=owner.replace_once(s,'int obj_state,p92_lock;','int obj_state,p92_lock,pdev_lock;void *pdev_comp_priv_obj[WLAN_UMAC_MAX_COMPONENTS];QDF_STATUS obj_status[WLAN_UMAC_MAX_COMPONENTS];')
 block=SUPPORT.replace('NATIVE_FREE',previous.previous.extract(native,NAMES[-1])).replace('NATIVE_DISPATCH','\n'.join(previous.previous.extract(native,n) for n in NAMES[:-1]))
 # Native component_detach has external linkage; declaration must match.
 block=block.replace('static QDF_STATUS p93_component_detach(', 'QDF_STATUS p93_component_detach(')
 destroy=previous.previous.function(s,'p92_destroy')
 replacement=destroy.replace('!p->q90_live','p->q90_live').replace('p92_destroyed++;return 0;','p92_destroyed++;p93_arm(p);p93_result=p93_native_destroy(p);return p93_result;')
 s=owner.replace_once(s,destroy,block+'\n'+replacement)
 finish=previous.previous.function(s,'p92_finish');s=owner.replace_once(s,finish,finish.replace('!p->q90_live','p->q90_live'))
 shutdown=previous.previous.function(s,'q90_shutdown').splitlines()[0]
 s=owner.replace_once(s,shutdown,shutdown.replace('q90_closed=true;','q90_closed=true;if(p92_enabled){p92_finish(&pdev);q90_atomic=old;return;}'))
 case=previous.previous.function(s,'p92_case')
 case=owner.replace_once(case,'p92_begin(&pdev,extra);','assert(!p93_heap);p93_parent=calloc(1,sizeof(*p93_parent));assert(p93_parent);p93_heap=1;p93_parent->psoc=&psoc;p93_parent->pdev_lock=1;p93_order=p93_free_step=p93_free_calls=p93_deinits=p93_bugs=0;p93_async=NULL;\n p92_begin(p93_parent,extra);p93_parent->pdev_objmgr.wlan_psoc=&psoc;')
 case=owner.replace_once(case,'}else assert(p92_destroyed==1 && !objects_live && !p89_heap);','}else {assert(p92_destroyed==1 && !objects_live && !p89_heap);q90_atomic=false;p93_completed();}')
 s=owner.replace_once(s,previous.previous.function(s,'p92_case'),case)
 # Only global lvalue syntax changes; arrow-based native bodies are preserved.
 s=owner.replace_once(s,'static struct wlan_objmgr_pdev pdev={.psoc=&psoc};','static struct wlan_objmgr_pdev p93_default={.psoc=&psoc};')
 s=re.sub(r'\bpdev\.', 'p93_parent->',s)
 s=re.sub(r'&pdev\b(?!->)', 'p93_parent',s)
 s=owner.replace_once(s,'static int create(struct mishare_runtime_owner **o) {','static int create(struct mishare_runtime_owner **o) {if(!p92_enabled)p93_parent=&p93_default;')
 cases=previous.previous.function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned mode=1;mode<=4;mode++)for(unsigned hold=0;hold<2;hold++) {
  pid_t c=fork();assert(c>=0);if(!c){p93_mode=mode;p92_case(trace,1,0,hold);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==56);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==40);','assert(count==40);\n'+extra))
 # Direct calls in inherited contracts can precede create().
 s=owner.replace_once(s,'int main(void) {','int main(void) {p93_parent=&p93_default;')
 for n in NAMES+previous.NAMES:assert s.count(previous.previous.extract(native,n))==1,n
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[('psoc_detach','wlan_objmgr_pdev_obj_free','wlan_objmgr_psoc_pdev_detach(pdev->pdev_objmgr.wlan_psoc, pdev)','QDF_STATUS_SUCCESS','EXPECTED_PDEV_PSOC_DETACH_BEFORE_LOCK',0),('lock_destroy','wlan_objmgr_pdev_obj_free','qdf_spinlock_destroy(&pdev->pdev_lock);','/* missing lock destroy */','EXPECTED_PDEV_LOCK_BEFORE_QUEUE',0),('queue_deinit','wlan_objmgr_pdev_obj_free','wlan_delayed_peer_obj_free_deinit(pdev);','/* missing queue deinit */','EXPECTED_PDEV_QUEUE_DEINIT_BEFORE_HEAP_FREE',0),('heap_free','wlan_objmgr_pdev_obj_free','qdf_mem_free(pdev);','/* missing actual parent free */','EXPECTED_PDEV_ACTUAL_HEAP_FREE',0),('component_order','wlan_objmgr_pdev_obj_destroy','for (id = 0; id < WLAN_UMAC_MAX_COMPONENTS; id++)','for (id = WLAN_UMAC_MAX_COMPONENTS; id-- > 0;)','EXPECTED_PDEV_FORWARD_COMPONENT_ORDER',0),('async_wait','wlan_objmgr_pdev_obj_destroy','if (obj_status == QDF_STATUS_COMP_ASYNC)','if (false)','EXPECTED_PDEV_ASYNC_COMPONENT_WAIT',1)]
 for label,name,needle,mutation,marker,mode in controls:
  target=owner.replace_once(source,previous.previous.function(source,'main'),f'int main(void) {{p93_mode={mode};p92_case(false,1,0,false);_Exit(0);}}')
  body=previous.previous.extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-600:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_PDEV_FREE_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_PDEV_function_sha256']={n:hashlib.sha256(previous.previous.extract((root/previous.parent.PDEV).read_text(),n).encode()).hexdigest() for n in previous.NAMES+NAMES}
 r['additional_composite_cases']=56;r['negative_controls_rejected']=11
 r['checks']=['0090 baseline plus 0092 forty parent/peer/VDEV cases now use actual heap PDEV storage and native final dispatcher/status/detach/free','sixteen additional parent component async, component failure, PSOC detach failure and bad async completion sequences under both VDEV trace modes with/without extra parent reference','native PDEV forward component dispatch and original async status gate; fixture delivers valid native component completion in process context to resume final free','native PDEV free calls modeled PSOC detach and lock destruction, original peer queue deinit/QDF cancellation, then actual host heap free in order; no explicit premature queue deinit by fixture caller','all five 0092 and six new native dispatcher/free mutations rejected']
 r['limitations']='Fixture caller integration, no production kernel changes or automatic shutdown coordinator. Heap PDEV allocation/setup, component registry/two sentinel handlers, PSOC detach, PDEV/list/lock and Linux workqueue endpoints remain models. Native PDEV create and real component implementations/PSOC lifetime are not executed. DP unmap producer and completion gate retain 0090 model boundaries. Only selected added cases enable heap/native parent integration; baseline uses static fallback. Failure children intentionally retain unfinished resources until process exit. No real concurrent late producers, peer trace parity, active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
