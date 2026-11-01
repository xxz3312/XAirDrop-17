#!/usr/bin/env python3
"""Actions-only delayed native peer queue and explicit caller drain contract."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_peer_fixture as previous
from mishare_recovery_fixture import function
owner=previous.owner
engine=previous.engine
PEER=previous.PEER
DEFER='qca-wifi-host-cmn/qdf/linux/src/qdf_defer.c'
PRIVATE='qca-wifi-host-cmn/qdf/linux/src/i_qdf_defer.h'
QUEUE=['wlan_objmgr_peer_obj_free_work','wlan_peer_obj_free_enqueue','wlan_objmgr_peer_obj_destroy','wlan_delayed_peer_obj_free_init','wlan_delayed_peer_obj_free_deinit']
PUBLIC_NAMES=['__qdf_defer_func','qdf_create_work','qdf_sched_work','qdf_destroy_work','qdf_flush_work']
PRIVATE_NAMES=['__qdf_init_work','__qdf_sched_work','__qdf_disable_work','__qdf_flush_work']
TYPES=r'''
#include <stddef.h>
typedef void *qdf_handle_t;
typedef void (*qdf_defer_fn_t)(void *);
typedef struct q90_node {struct q90_node *next;bool queued;} qdf_list_node_t;
typedef struct {qdf_list_node_t *head,*tail;unsigned count,capacity;} qdf_list_t;
struct work_struct {bool initialized,pending,running;unsigned runs,cancels;void (*callback)(struct work_struct *);};
typedef struct {struct work_struct work;qdf_defer_fn_t fn;void *arg;} __qdf_work_t;
typedef __qdf_work_t qdf_work_t;
'''
SUPPORT=r'''
#define MAX_DELAYED_FREE_PEERS 64
#define QDF_STATUS_E_ALREADY 104
static unsigned q90_mode,q90_lock_depth,q90_schedules,q90_coalesced,q90_dropped,q90_unit_calls;
static bool q90_atomic,q90_inline_worker,q90_unit,q90_closed,q90_bad_pdev_seen,q90_cancel_seen;
static struct wlan_objmgr_peer *q90_unit_next;
static QDF_STATUS q90_native_enqueue(struct wlan_objmgr_peer *);
static void q90_run(struct work_struct *);
static void q90_init_linux(struct work_struct *w,void (*fn)(struct work_struct *)) {assert(!w->running && !w->pending);memset(w,0,sizeof(*w));w->initialized=true;w->callback=fn;}
static bool q90_schedule(struct work_struct *w) {assert(w->initialized && !q90_lock_depth);q90_schedules++;if(w->pending){q90_coalesced++;return false;}w->pending=true;if(q90_inline_worker && !w->running){bool old=q90_atomic;q90_atomic=false;q90_run(w);q90_atomic=old;}return true;}
static bool q90_cancel(struct work_struct *w) {assert(w->initialized && !q90_atomic && !w->running && "EXPECTED_QUEUE_NO_SELF_CANCEL");bool pending=w->pending;w->pending=false;w->cancels+=pending;return pending;}
static void q90_flush(struct work_struct *w) {assert(w->initialized && !q90_atomic && !w->running);if(w->pending)q90_run(w);}
static void q90_run(struct work_struct *w) {assert(w->initialized && w->pending && !w->running && !q90_atomic && !q90_lock_depth);w->pending=false;w->running=true;w->runs++;w->callback(w);w->running=false;}
static void q90_lock_create(int *lock) {assert(!*lock);*lock=1;}
static void q90_lock(int *lock) {assert(*lock==1 && !q90_lock_depth);q90_lock_depth=1;}
static void q90_unlock(int *lock) {assert(*lock==1 && q90_lock_depth==1);q90_lock_depth=0;}
static void q90_lock_destroy(int *lock) {struct wlan_objmgr_pdev *p=(void *)((char *)lock - offsetof(struct wlan_objmgr_pdev,peer_free_lock));assert(*lock==1 && !q90_lock_depth && !p->peer_free_list.count && !p->peer_obj_free_work.work.pending && !p->peer_obj_free_work.work.running && "EXPECTED_PEER_QUEUE_DEINIT_QUIESCENCE");*lock=0;}
static void q90_list_create(qdf_list_t *l,unsigned cap) {assert(cap==64);memset(l,0,sizeof(*l));l->capacity=cap;}
static bool q90_list_empty(qdf_list_t *l) {return !l->count;}
static unsigned q90_list_size(qdf_list_t *l) {return l->count;}
static QDF_STATUS q90_insert(qdf_list_t *l,qdf_list_node_t *n) {assert(q90_lock_depth && !n->queued);if(l->count==l->capacity){q90_dropped++;return QDF_STATUS_E_FAILURE;}n->next=NULL;n->queued=true;if(l->tail)l->tail->next=n;else l->head=n;l->tail=n;l->count++;return QDF_STATUS_SUCCESS;}
static void q90_remove(qdf_list_t *l,qdf_list_node_t **n) {assert(q90_lock_depth && l->count && l->head);*n=l->head;l->head=(*n)->next;if(!--l->count)l->tail=NULL;(*n)->next=NULL;(*n)->queued=false;}
static bool qdf_in_atomic(void) {return q90_atomic;}
static struct wlan_objmgr_pdev *q90_get_pdev(struct wlan_objmgr_vdev *v) {if(q90_mode==3 && !q90_bad_pdev_seen){q90_bad_pdev_seen=true;return NULL;}return wlan_vdev_get_pdev(v);}
static QDF_STATUS q90_dispatch(struct wlan_objmgr_peer *p) {assert(!q90_lock_depth && "EXPECTED_PEER_WORK_UNLOCK");if(q90_unit){assert(p && !p->free_node.queued);q90_unit_calls++;if(q90_unit_next){struct wlan_objmgr_peer *next=q90_unit_next;q90_unit_next=NULL;assert(!q90_native_enqueue(next));}return QDF_STATUS_SUCCESS;}return p89_native_destroy_body(p);}
#define container_of(p,type,member) ((type *)((char *)(p)-offsetof(type,member)))
#define qdf_container_of container_of
#define INIT_WORK(w,fn) q90_init_linux(w,fn)
#define schedule_work q90_schedule
#define cancel_work_sync q90_cancel
#define flush_work q90_flush
#define QDF_TRACE(...) ((void)0)
#define __qdf_defer_func q90_defer_func
#define __qdf_init_work q90_init_work
#define __qdf_sched_work q90_sched_work
#define __qdf_disable_work q90_disable_work
#define __qdf_flush_work q90_flush_work
#define qdf_create_work q90_qdf_create_work
#define qdf_sched_work q90_qdf_sched_work
#define qdf_destroy_work q90_qdf_destroy_work
#define qdf_flush_work q90_qdf_flush_work
NATIVE_QDF_FUNCTIONS
#undef flush_work
#undef cancel_work_sync
#undef schedule_work
#undef INIT_WORK
#undef QDF_TRACE
#pragma push_macro("qdf_spinlock_destroy")
#pragma push_macro("__wlan_objmgr_peer_obj_destroy")
#undef qdf_spinlock_destroy
#undef __wlan_objmgr_peer_obj_destroy
#define qdf_spinlock_create q90_lock_create
#define qdf_spin_lock_bh q90_lock
#define qdf_spin_unlock_bh q90_unlock
#define qdf_spinlock_destroy q90_lock_destroy
#define qdf_list_create q90_list_create
#define qdf_list_empty q90_list_empty
#define qdf_list_size q90_list_size
#define qdf_list_insert_back q90_insert
#define qdf_list_remove_front q90_remove
#define __wlan_objmgr_peer_obj_destroy q90_dispatch
#define wlan_vdev_get_pdev q90_get_pdev
#define wlan_objmgr_peer_obj_free_work q90_native_worker
#define wlan_peer_obj_free_enqueue q90_native_enqueue
#define wlan_delayed_peer_obj_free_init q90_native_init
#define wlan_delayed_peer_obj_free_deinit q90_native_deinit
NATIVE_QUEUE_FUNCTIONS
#undef wlan_delayed_peer_obj_free_deinit
#undef wlan_delayed_peer_obj_free_init
#undef wlan_peer_obj_free_enqueue
#undef wlan_objmgr_peer_obj_free_work
#undef wlan_vdev_get_pdev
#undef __wlan_objmgr_peer_obj_destroy
#undef qdf_list_remove_front
#undef qdf_list_insert_back
#undef qdf_list_size
#undef qdf_list_empty
#undef qdf_list_create
#undef qdf_spinlock_destroy
#undef qdf_spin_unlock_bh
#undef qdf_spin_lock_bh
#undef qdf_spinlock_create
#pragma pop_macro("__wlan_objmgr_peer_obj_destroy")
#pragma pop_macro("qdf_spinlock_destroy")
#undef qdf_flush_work
#undef qdf_destroy_work
#undef qdf_sched_work
#undef qdf_create_work
#undef __qdf_flush_work
#undef __qdf_disable_work
#undef __qdf_sched_work
#undef __qdf_init_work
#undef __qdf_defer_func
static void q90_initialize(struct wlan_objmgr_pdev *p) {assert(!p->q90_live);assert(!q90_native_init(p));p->q90_live=true;}
static int q90_try_deinit(struct wlan_objmgr_pdev *p) {
 if(!p->q90_live)return 0;
 if(!q90_closed || p->peer_obj_free_work.work.pending || p->peer_obj_free_work.work.running || p->peer_free_list.count)return -EINPROGRESS;
 assert(!q90_atomic);assert(!q90_native_deinit(p));p->q90_live=false;return 0;
}
'''
LATE=r'''
static void q90_drain(struct mishare_runtime_owner **o) {
 struct wlan_objmgr_pdev *p=&pdev;struct work_struct *w=&p->peer_obj_free_work.work;
 if(!p->peer_free_list.count && !w->pending)return;
 assert(w->pending && ctx_peer && p89_heap==1 && !p89_destroy_calls && ctx_peer->peer_objmgr.ref_cnt.value==0 && p89_vdev_link && p89_psoc_link && p89_free_calls==0 && "EXPECTED_PEER_WORK_SCHEDULE");
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls && !detach_calls && engine_allocations==1 && dp_objects);
 bool old=q90_atomic;q90_atomic=false;
 if(q90_mode==2) {q90_closed=true;assert(q90_try_deinit(p)==-EINPROGRESS && p->q90_live && p->peer_free_list.count==1 && "EXPECTED_PEER_QUEUE_DEINIT_QUIESCENCE");}
 if(q90_mode==5 && !q90_cancel_seen) {
  q90_cancel_seen=true;q90_qdf_destroy_work(0,&p->peer_obj_free_work);
  assert(!w->pending && p->peer_free_list.count==1 && ctx_peer && p89_heap==1 && !p89_free_calls && p89_vdev_link && "EXPECTED_WORK_CANCEL_NOT_DRAIN");
  assert(q90_qdf_sched_work(0,&p->peer_obj_free_work));
 }
 unsigned limit=0;
 while(w->pending && limit++<4) {q90_qdf_flush_work(&p->peer_obj_free_work);}
 assert(!w->pending && !w->running && !p->peer_free_list.count && "EXPECTED_PEER_WORK_DRAIN");
 assert(p89_destroy_calls==1 && "EXPECTED_PEER_WORK_DISPATCH");
 if(q90_mode==2)assert(!q90_try_deinit(p));
 q90_atomic=old;
}
static void q90_shutdown(void) {bool old=q90_atomic;q90_atomic=false;q90_closed=true;assert(!q90_try_deinit(&pdev) && !pdev.peer_obj_free_work.work.running && !pdev.peer_obj_free_work.work.pending && !pdev.peer_free_list.count);q90_atomic=old;}
'''
EXTRA=r'''
static void q90_contracts(void) {
 assert(q90_native_init(NULL)==QDF_STATUS_E_FAILURE && q90_native_deinit(NULL)==QDF_STATUS_E_FAILURE && q90_native_enqueue(NULL)==QDF_STATUS_E_FAILURE);q90_native_worker(NULL);
 /* Two entries coalesce to one invocation: active_work_cnt is not a per-peer
  * quiescence proof, so the explicit caller checks work and list state. */
 for(unsigned kind=0;kind<3;kind++) {
  struct wlan_objmgr_pdev p={0};struct wlan_objmgr_vdev v={0};struct wlan_objmgr_peer peers[2]={0};v.pdev=&p;peers[0].vdev=peers[1].vdev=&v;
  q90_initialize(&p);q90_unit=true;q90_unit_calls=0;unsigned drops=q90_dropped;
  if(kind==1)p.peer_free_list.capacity=1;
  assert(!q90_native_enqueue(&peers[0]));
  if(kind==2)q90_unit_next=&peers[1];else assert(!q90_native_enqueue(&peers[1]));
  assert(p.peer_obj_free_work.work.pending);
  q90_qdf_flush_work(&p.peer_obj_free_work);
  if(kind==0)assert(q90_unit_calls==2 && !p.peer_free_list.count && !p.peer_obj_free_work.work.pending && p.active_work_cnt==1);
  if(kind==1)assert(q90_unit_calls==1 && q90_dropped==drops+1 && !peers[1].free_node.queued && p.active_work_cnt==1);
  if(kind==2){assert(q90_unit_calls==2 && !p.peer_free_list.count && p.peer_obj_free_work.work.pending && p.active_work_cnt==1);q90_qdf_flush_work(&p.peer_obj_free_work);assert(!p.peer_obj_free_work.work.pending && !p.active_work_cnt && p.peer_obj_free_work.work.runs==2);}
  q90_closed=true;assert(!q90_try_deinit(&p));q90_closed=false;q90_unit=false;
 }
 __qdf_work_t empty={0};assert(!q90_qdf_create_work(0,&empty,NULL,NULL));q90_defer_func(&empty.work);
}
static void q90_extra_cases(void) {
 for(unsigned mode=1;mode<=9;mode++)for(unsigned early=0;early<2;early++){pid_t c=fork();assert(c>=0);if(!c){q90_mode=mode;q90_atomic=mode!=4;q90_inline_worker=mode==9;p89_mode=mode==6?1:mode==7?2:mode==8?6:0;clean_modes=early?2:0;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''

def extract(text,name):
 m=re.search(r'(?:static\s+)?(?:inline\s+)?(?:void|bool|QDF_STATUS|uint32_t)\s+'+name+r'\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)
 if not m:raise ValueError('Missing queue source function: '+name)
 return m[0]

def delayed_destroy(text):
 variants=re.findall(r'(?:static\s+)?QDF_STATUS\s+wlan_objmgr_peer_obj_destroy\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)
 assert len(variants)==2 and 'qdf_in_atomic()' in variants[0]
 return variants[0]

def fixture(root):
 source,exits,stubbed=previous.fixture(root);peer=(root/PEER).read_text();defer=(root/DEFER).read_text();private=(root/PRIVATE).read_text()
 source=owner.replace_once(source,'struct wlan_objmgr_pdev {',TYPES+'\nstruct wlan_objmgr_pdev {')
 source=owner.replace_once(source,'int p89_lock,p89_peer_count;','int p89_lock,p89_peer_count;int peer_free_lock;qdf_list_t peer_free_list;qdf_work_t peer_obj_free_work;unsigned active_work_cnt;bool q90_live;')
 source=owner.replace_once(source,'struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;','struct wlan_objmgr_peer {qdf_list_node_t free_node;struct wlan_objmgr_vdev *vdev;')
 qdf='\n'.join([extract(defer,'__qdf_defer_func')]+[extract(private,n) for n in PRIVATE_NAMES]+[extract(defer,n) for n in PUBLIC_NAMES[1:]])
 queue='\n'.join(extract(peer,n) if n!='wlan_objmgr_peer_obj_destroy' else delayed_destroy(peer) for n in QUEUE)
 block=SUPPORT.replace('\nNATIVE_QDF_FUNCTIONS\n','\n'+qdf+'\n').replace('\nNATIVE_QUEUE_FUNCTIONS\n','\n'+queue+'\n')
 source=owner.replace_once(source,previous.direct_destroy(peer),block)
 create=function(source,'p89_create');source=owner.replace_once(source,create,create.replace('{','{\n q90_initialize(v->pdev);',1))
 source=owner.replace_once(source,'static bool p89_complete(',LATE+'\nstatic bool p89_complete(')
 complete=function(source,'p89_complete');changed=complete.replace('{','{\n q90_drain(o);',1)
 changed=owner.replace_once(changed,'clean_peer_unmap();}','clean_peer_unmap();q90_drain(o);}')
 changed=owner.replace_once(changed,'p89_native_release(ctx_peer,REF_NATIVE_OSIF);','p89_native_release(ctx_peer,REF_NATIVE_OSIF);q90_drain(o);')
 source=owner.replace_once(source,complete,changed)
 clean=function(source,'clean_end');source=owner.replace_once(source,clean,owner.replace_once(clean,'if(!ref_finish(o,ret,held,hold))return;','if(!ref_finish(o,ret,held,hold)){return;}\n q90_shutdown();'))
 baseline=function(source,'ref_baseline');source=owner.replace_once(source,baseline,EXTRA+'\n'+owner.replace_once(baseline,'p89_extra_cases();','p89_extra_cases();q90_extra_cases();'))
 main=function(source,'main');source=owner.replace_once(source,main,owner.replace_once(main,'for(unsigned trace=0;','q90_contracts();for(unsigned trace=0;'))
 for n in QUEUE:assert source.count(delayed_destroy(peer) if n=='wlan_objmgr_peer_obj_destroy' else extract(peer,n))==1,n
 for n in PUBLIC_NAMES:assert source.count(extract(defer,n))==1,n
 for n in PRIVATE_NAMES:assert source.count(extract(private,n))==1,n
 return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[('queue_schedule','wlan_peer_obj_free_enqueue','qdf_sched_work(0, &pdev->peer_obj_free_work);','/* negative: omit queue submission */','EXPECTED_PEER_WORK_SCHEDULE',1),('worker_unlock','wlan_objmgr_peer_obj_free_work','qdf_spin_unlock_bh(&pdev->peer_free_lock);\n\n\t\tpeer =','/* negative: keep list lock during peer destructor */\n\n\t\tpeer =','EXPECTED_PEER_WORK_UNLOCK',1),('worker_dispatch','wlan_objmgr_peer_obj_free_work','__wlan_objmgr_peer_obj_destroy(peer);','/* negative: drop peer destructor */','EXPECTED_PEER_WORK_DISPATCH',1),('caller_flush','q90_drain','q90_qdf_flush_work(&p->peer_obj_free_work);','/* negative: omit explicit flush */','EXPECTED_PEER_WORK_DRAIN',1),('deinit_quiescence','q90_try_deinit','if(!q90_closed || p->peer_obj_free_work.work.pending || p->peer_obj_free_work.work.running || p->peer_free_list.count)','if(false)','EXPECTED_PEER_QUEUE_DEINIT_QUIESCENCE',2),('cancel_not_flush','qdf_destroy_work','__qdf_disable_work(work);','__qdf_flush_work(work);','EXPECTED_WORK_CANCEL_NOT_DRAIN',5)]
 for label,name,needle,mutation,marker,mode in controls:
  target=owner.replace_once(source,function(source,'main'),f'int main(void) {{q90_mode={mode};q90_atomic=true;engine_cycle(5240,false,0);_Exit(0);}}');c_file.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=60,env=env)
  body=extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-400:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_PEER_QUEUE_FIXTURE_PASS_ONLY'
 r['native_queue_function_sha256']={n:hashlib.sha256((delayed_destroy((root/PEER).read_text()) if n=='wlan_objmgr_peer_obj_destroy' else extract((root/PEER).read_text(),n)).encode()).hexdigest() for n in QUEUE}
 r['native_QDF_function_sha256']={n:hashlib.sha256(extract((root/(DEFER if n in PUBLIC_NAMES else PRIVATE)).read_text(),n).encode()).hexdigest() for n in PUBLIC_NAMES+PRIVATE_NAMES}
 prior=previous.previous.PARENT_CONTROLS+[label+suffix for suffix in ['','_debug'] for label in ['last_reference','reference_id_gate','reference_accounting','reference_admission']]+['logical_delete_reference_release','peer_last_reference','peer_component_order','peer_async_wait','peer_parent_pin','peer_parent_put']
 for n in prior+['queue_schedule','worker_unlock','worker_dispatch','caller_flush','deinit_quiescence','cancel_not_flush']:r['negative_control_'+n+'_rejected']=True
 r['checks']=['five original delayed peer worker/enqueue/destroy/init/deinit bodies and nine original QDF/Linux-adapter wrapper bodies execute; Linux primitives remain models','0089 complete suite retained under both VDEV trace modes with non-atomic delayed-wrapper direct path; 36 extra full cases cover queued/manual flush, deinit refusal, enqueue validation fallback, non-atomic direct, explicit cancel/resubmit, async component, component failure, extra peer hold and immediate worker','queued zero-ref peer retains heap, VDEV peer pin, DP ownership and native SM before explicit worker execution; worker drops list lock around actual 0089 peer destructor','explicit qualified caller closes producers, flushes bounded generations until work and list are empty, then native deinit cancels only idle work; caller contract is not wired into production shutdown','native QDF destroy reaches cancel_work_sync and does not drain list; explicit cancellation case retains peer and resubmits before process-context flush','unit list contracts preserve native coalescing residue: two enqueues/one work leaves active_work_cnt=1; running requeue needs a second flush generation','unit capacity failure is intentionally observed: original enqueue ignores failed list insertion, returns SUCCESS and overcounts; full/saturated native queues are not certified','all prior twenty-nine negatives and six schedule/unlock/dispatch/caller-flush/deinit/cancel-semantics mutations rejected']
 r['limitations']='Executes original FEATURE_DELAYED_PEER_OBJ_DESTROY branch and original QDF work adapters in an Actions host fixture. schedule_work/flush_work/cancel_work_sync, lists and locks are deterministic platform models; no Linux kworker concurrency or real QDF allocation failure certification. Full pipeline has one private self peer; multi-entry coalescing, requeue and capacity diagnostics use fake peer destructor leaves. Original active_work_cnt is not an exact peer/quiescence count under coalescing, and original enqueue ignores list-insert failure; these behaviors are recorded rather than fixed or used to authorize teardown. The explicit producer-closed/drain/deinit gate is a fixture caller contract, not a new production shutdown coordinator. qdf_destroy_work cancels synchronously but does not drain, and self-cancel/running teardown is excluded. Parent PDEV/PSOC storage and locks remain harness-retained; actual last-parent-reference destruction from inside a worker, global late producers, peer trace configuration, the real DP unmap graph and safe native unload remain unverified. All 0089 native-peer-component/attachment/platform endpoint boundaries remain. Failure children keep remaining resources until process exit. No active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop proof.'
 return r

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
