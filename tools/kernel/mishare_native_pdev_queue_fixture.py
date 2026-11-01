#!/usr/bin/env python3
"""Actions-only native PDEV reference lease across a delayed peer worker."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_native_peer_queue_fixture as queue
import mishare_native_refs_fixture as refs
PIN='36df473046706a5259942e1bf7222108dbbb860f'
PDEV='qca-wifi-host-cmn/umac/cmn_services/obj_mgr/src/wlan_objmgr_pdev_obj.c'
NAMES=['wlan_objmgr_pdev_get_ref','wlan_objmgr_pdev_try_get_ref','wlan_objmgr_pdev_release_ref','wlan_objmgr_pdev_vdev_attach','wlan_objmgr_pdev_vdev_detach','wlan_objmgr_pdev_obj_delete','wlan_objmgr_pdev_obj_free']
PREFIX=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int QDF_STATUS;
#define QDF_STATUS_SUCCESS 0
#define QDF_STATUS_E_FAILURE 1
#define QDF_STATUS_E_RESOURCES 2
#define QDF_STATUS_E_ALREADY 3
#define WLAN_OBJ_STATE_CREATED 1
#define WLAN_OBJ_STATE_LOGICALLY_DELETED 2
#define WLAN_OBJMGR_RATELIMIT_THRESH 2
#define QDF_TRACE_LEVEL_DEBUG 1
#define QDF_TRACE_LEVEL_FATAL 2
#define WLAN_PDEV_OP 1
#define MAX_DELAYED_FREE_PEERS 64
#define QDF_MAC_ADDR_FMT "%p"
#define QDF_MAC_ADDR_REF(p) ((void *)(p))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define qdf_container_of container_of
#define QDF_ASSERT(x) assert(x)
static void log_message(const char *fmt,...) {(void)fmt;}
#define obj_mgr_err log_message
#define obj_mgr_debug log_message
#define QDF_TRACE(...) ((void)0)
typedef struct {int value;} qdf_atomic_t;
static unsigned bugs,destroys,heap_pdev,heap_vdev,heap_peer,steps;
static bool expect_bug,atomic_entry,eager,closed,detached;
static struct wlan_objmgr_peer *next_peer;
static void bug(int x) {assert(!x && expect_bug);bugs++;}
#define WLAN_OBJMGR_BUG bug
static void qdf_atomic_inc(qdf_atomic_t *v) {v->value++;}
static void qdf_atomic_dec(qdf_atomic_t *v) {assert(v->value>0 && "EXPECTED_PDEV_REFERENCE_ID_GATE");v->value--;}
static int qdf_atomic_read(qdf_atomic_t *v) {return v->value;}
static bool qdf_atomic_dec_and_test(qdf_atomic_t *v) {assert(v->value>0);return !--v->value;}
REF_ENUM
WORK_TYPES
struct wlan_objmgr_psoc {int live;};
struct vdev_list {struct wlan_objmgr_vdev *head;};
struct wlan_objmgr_pdev {struct {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt,wlan_pdev_id,wlan_vdev_count,max_vdev_count;struct vdev_list wlan_vdev_list;struct wlan_objmgr_psoc *wlan_psoc;} pdev_objmgr;int obj_state,pdev_lock,peer_free_lock;qdf_list_t peer_free_list;qdf_work_t peer_obj_free_work;unsigned active_work_cnt;};
struct wlan_objmgr_vdev {struct wlan_objmgr_pdev *pdev;struct wlan_objmgr_vdev *next;};
struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;qdf_list_node_t free_node;uint8_t mac[6];};
static QDF_STATUS wlan_objmgr_pdev_obj_destroy(struct wlan_objmgr_pdev *);
static QDF_STATUS wlan_objmgr_pdev_vdev_detach(struct wlan_objmgr_pdev *,struct wlan_objmgr_vdev *);
static QDF_STATUS wlan_peer_obj_free_enqueue(struct wlan_objmgr_peer *);
static void wlan_objmgr_pdev_release_ref(struct wlan_objmgr_pdev *,wlan_objmgr_ref_dbgid);
static QDF_STATUS __wlan_objmgr_peer_obj_destroy(struct wlan_objmgr_peer *peer) {
 struct wlan_objmgr_vdev *v=peer->vdev;struct wlan_objmgr_pdev *p=v->pdev;
 assert(!p->peer_free_lock || p->peer_free_lock==1);
 assert(!wlan_objmgr_pdev_vdev_detach(p,v));
 free(v);heap_vdev--;free(peer);heap_peer--;
 if(next_peer){struct wlan_objmgr_peer *next=next_peer;next_peer=NULL;assert(!wlan_peer_obj_free_enqueue(next));}
 return QDF_STATUS_SUCCESS;
}
static void wlan_pdev_obj_lock(struct wlan_objmgr_pdev *p) {assert(p->pdev_lock==1);p->pdev_lock=2;}
static void wlan_pdev_obj_unlock(struct wlan_objmgr_pdev *p) {assert(p->pdev_lock==2);p->pdev_lock=1;}
static uint8_t wlan_objmgr_pdev_get_pdev_id(struct wlan_objmgr_pdev *p) {return p->pdev_objmgr.wlan_pdev_id;}
static void wlan_objmgr_print_ref_ids(qdf_atomic_t *v,int level) {(void)v;(void)level;}
static int qdf_get_pidx(void) {return 0;}
static void wlan_objmgr_notify_log_delete(struct wlan_objmgr_pdev *p,int type) {assert(type==WLAN_PDEV_OP && p->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && p->pdev_lock==1);}
static void wlan_obj_pdev_vdevlist_add_tail(struct vdev_list *l,struct wlan_objmgr_vdev *v) {assert(!v->next);if(!l->head){l->head=v;return;}struct wlan_objmgr_vdev *n=l->head;while(n->next)n=n->next;n->next=v;}
static void wlan_obj_pdev_vdevlist_remove_vdev(struct vdev_list *l,struct wlan_objmgr_vdev *v) {struct wlan_objmgr_vdev **n=&l->head;while(*n && *n!=v)n=&(*n)->next;assert(*n==v);*n=v->next;v->next=NULL;}
static void qdf_spinlock_create(int *lock) {assert(!*lock);*lock=1;}
static void qdf_spin_lock_bh(int *lock) {assert(*lock==1);*lock=2;}
static void qdf_spin_unlock_bh(int *lock) {assert(*lock==2);*lock=1;}
static void qdf_spinlock_destroy(int *lock) {assert(*lock==1 && detached);if(steps==1){steps=2;}else {assert(steps==3);steps=4;}*lock=0;}
static void qdf_list_create(qdf_list_t *l,unsigned cap) {memset(l,0,sizeof(*l));l->capacity=cap;}
static bool qdf_list_empty(qdf_list_t *l) {return !l->count;}
static unsigned qdf_list_size(qdf_list_t *l) {return l->count;}
static QDF_STATUS qdf_list_insert_back(qdf_list_t *l,qdf_list_node_t *n) {assert(!n->queued && l->count<l->capacity);n->queued=true;n->next=NULL;if(l->tail)l->tail->next=n;else l->head=n;l->tail=n;l->count++;return 0;}
static void qdf_list_remove_front(qdf_list_t *l,qdf_list_node_t **n) {assert(l->head && l->count);*n=l->head;l->head=(*n)->next;if(!--l->count)l->tail=NULL;(*n)->next=NULL;(*n)->queued=false;}
static struct wlan_objmgr_vdev *wlan_peer_get_vdev(struct wlan_objmgr_peer *p) {return p->vdev;}
static uint8_t *wlan_peer_get_macaddr(struct wlan_objmgr_peer *p) {return p->mac;}
static struct wlan_objmgr_pdev *wlan_vdev_get_pdev(struct wlan_objmgr_vdev *v) {return v->pdev;}
static bool qdf_in_atomic(void) {return atomic_entry;}
static void run_work(struct work_struct *w) {assert(w->initialized && w->pending && !w->running);bool old=atomic_entry;atomic_entry=false;w->pending=false;w->running=true;w->runs++;w->callback(w);w->running=false;atomic_entry=old;}
static void initialize_work(struct work_struct *w,void (*fn)(struct work_struct *)) {w->initialized=true;w->callback=fn;}
#define INIT_WORK initialize_work
static bool schedule_work(struct work_struct *w) {assert(w->initialized);if(w->pending)return false;w->pending=true;if(eager && !w->running)run_work(w);return true;}
static void flush_work(struct work_struct *w) {assert(!atomic_entry && !w->running);if(w->pending)run_work(w);}
static bool cancel_work_sync(struct work_struct *w) {assert(!atomic_entry && !w->running && "EXPECTED_PDEV_WORKER_PARENT_LEASE");bool pending=w->pending;w->pending=false;if(steps==2){assert(!pending);steps=3;}return pending;}
NATIVE_WORK
NATIVE_QUEUE
static QDF_STATUS wlan_objmgr_psoc_pdev_detach(struct wlan_objmgr_psoc *s,struct wlan_objmgr_pdev *p) {assert(s && s->live && p->pdev_objmgr.wlan_psoc==s && !steps);detached=true;steps=1;return 0;}
static void pdev_memory_free(struct wlan_objmgr_pdev *p) {assert(steps==4 && !p->pdev_lock && !p->peer_free_lock && !p->peer_obj_free_work.work.pending && !p->peer_obj_free_work.work.running && !p->peer_free_list.count);steps=5;heap_pdev--;free(p);}
#define qdf_mem_free pdev_memory_free
NATIVE_PDEV
#undef qdf_mem_free
static void check_refs(struct wlan_objmgr_pdev *p,int expected,const char *marker) {int sum=0;for(unsigned i=0;i<WLAN_REF_ID_MAX;i++){assert(p->pdev_objmgr.ref_id_dbg[i].value>=0);sum+=p->pdev_objmgr.ref_id_dbg[i].value;}if(sum!=expected || p->pdev_objmgr.ref_cnt.value!=sum){fprintf(stderr,"%s\n",marker);abort();}}
static QDF_STATUS wlan_objmgr_pdev_obj_destroy(struct wlan_objmgr_pdev *p) {
 assert(!p->peer_obj_free_work.work.running && "EXPECTED_PDEV_WORKER_PARENT_LEASE");
 assert(closed && "EXPECTED_PDEV_PRODUCER_CLOSED");
 assert(!p->peer_obj_free_work.work.pending && !p->peer_free_list.count && !p->pdev_objmgr.wlan_vdev_count && !p->pdev_objmgr.wlan_vdev_list.head && !heap_peer && !heap_vdev);
 check_refs(p,0,"EXPECTED_PDEV_FINAL_REFERENCE_ACCOUNTING");destroys++;return wlan_objmgr_pdev_obj_free(p);
}
static struct wlan_objmgr_pdev *make_parent(struct wlan_objmgr_psoc *s) {struct wlan_objmgr_pdev *p=calloc(1,sizeof(*p));assert(p);heap_pdev++;p->pdev_lock=1;p->obj_state=WLAN_OBJ_STATE_CREATED;p->pdev_objmgr.max_vdev_count=2;p->pdev_objmgr.wlan_psoc=s;assert(!wlan_delayed_peer_obj_free_init(p));wlan_objmgr_pdev_get_ref(p,WLAN_OBJMGR_ID);return p;}
static struct wlan_objmgr_peer *make_peer(struct wlan_objmgr_pdev *p) {struct wlan_objmgr_peer *n=calloc(1,sizeof(*n));assert(n);heap_peer++;n->vdev=calloc(1,sizeof(*n->vdev));assert(n->vdev);heap_vdev++;n->vdev->pdev=p;assert(!wlan_objmgr_pdev_vdev_attach(p,n->vdev));return n;}
static void drain(struct wlan_objmgr_pdev *p) {bool old=atomic_entry;atomic_entry=false;unsigned limit=0;while(p->peer_obj_free_work.work.pending && limit++<4)qdf_flush_work(&p->peer_obj_free_work);atomic_entry=old;}
static void finish_parent(struct wlan_objmgr_pdev *p,bool extra,bool reverse) {
 closed=true;
 drain(p);
 assert(!p->peer_obj_free_work.work.running && !p->peer_obj_free_work.work.pending && !p->peer_free_list.count && !p->pdev_objmgr.wlan_vdev_count && "EXPECTED_PDEV_WORK_DRAIN");
 check_refs(p,extra?2:1,"EXPECTED_PDEV_DETACH_REFERENCE");
 atomic_entry=false;
 if(extra && reverse)wlan_objmgr_pdev_release_ref(p,WLAN_OSIF_ID);
 wlan_objmgr_pdev_release_ref(p,WLAN_HDD_ID_OBJ_MGR);
 if(extra && !reverse){assert(!destroys);wlan_objmgr_pdev_release_ref(p,WLAN_OSIF_ID);}
 assert(destroys==1 && !heap_pdev && !heap_peer && !heap_vdev && steps==5 && "EXPECTED_PDEV_FINAL_RELEASE");
}
static void one_case(unsigned count,bool atomic,bool immediate,bool delete_first,bool extra,bool reverse,bool cancel) {
 assert(!heap_pdev && !heap_vdev && !heap_peer);destroys=steps=0;closed=detached=false;next_peer=NULL;atomic_entry=atomic;eager=immediate;struct wlan_objmgr_psoc s={1};struct wlan_objmgr_pdev *p=make_parent(&s);
 struct wlan_objmgr_peer *a=make_peer(p),*b=count==2?make_peer(p):NULL;
 assert(wlan_objmgr_pdev_try_get_ref(p,WLAN_HDD_ID_OBJ_MGR)==QDF_STATUS_SUCCESS);
 if(extra)assert(!wlan_objmgr_pdev_try_get_ref(p,WLAN_OSIF_ID));
 check_refs(p,2+(int)count+(int)extra,"EXPECTED_PDEV_ATTACH_REFERENCE");
 if(delete_first){assert(!wlan_objmgr_pdev_obj_delete(p));assert(wlan_objmgr_pdev_try_get_ref(p,WLAN_SCAN_ID)==QDF_STATUS_E_RESOURCES && "EXPECTED_PDEV_REFERENCE_ADMISSION");}
 if(b && atomic){next_peer=b;b=NULL;}
 assert(!wlan_objmgr_peer_obj_destroy(a));if(b)assert(!wlan_objmgr_peer_obj_destroy(b));
 if(cancel){bool old=atomic_entry;atomic_entry=false;qdf_destroy_work(0,&p->peer_obj_free_work);assert(!p->peer_obj_free_work.work.pending && p->peer_free_list.count==1 && heap_peer==1);assert(qdf_sched_work(0,&p->peer_obj_free_work));atomic_entry=old;}
 if(!delete_first){assert(!wlan_objmgr_pdev_obj_delete(p));assert(wlan_objmgr_pdev_try_get_ref(p,WLAN_SCAN_ID)==QDF_STATUS_E_RESOURCES && "EXPECTED_PDEV_REFERENCE_ADMISSION");}
 assert(!destroys && heap_pdev==1 && p->pdev_objmgr.ref_id_dbg[WLAN_HDD_ID_OBJ_MGR].value==1 && "EXPECTED_PDEV_COORDINATOR_HOLD");
 finish_parent(p,extra,reverse);
}
static void invalid_reference(void) {destroys=steps=0;closed=detached=false;atomic_entry=eager=false;struct wlan_objmgr_psoc s={1};struct wlan_objmgr_pdev *p=make_parent(&s);unsigned before=bugs;expect_bug=true;wlan_objmgr_pdev_release_ref(p,WLAN_SCAN_ID);expect_bug=false;assert(bugs==before+1);check_refs(p,1,"EXPECTED_PDEV_REFERENCE_ID_GATE");closed=true;assert(!wlan_objmgr_pdev_obj_delete(p));assert(destroys==1 && !heap_pdev);}
int main(void) {
 unsigned cases=0;
 for(unsigned n=1;n<=2;n++)for(unsigned a=0;a<2;a++)for(unsigned e=0;e<2;e++)for(unsigned first=0;first<2;first++)for(unsigned extra=0;extra<2;extra++)for(unsigned reverse=0;reverse<(extra?2u:1u);reverse++){one_case(n,a,e,first,extra,reverse,false);cases++;}
 one_case(1,true,false,true,false,false,true);one_case(1,true,false,true,true,false,true);cases+=2;assert(cases==50);invalid_reference();
 puts("MISHARE_NATIVE_PDEV_QUEUE_LEASE_FIXTURE_PASS_ONLY");return 0;
}
'''

def fixture(root):
 pdev=(root/PDEV).read_text();peer=(root/queue.PEER).read_text();defer=(root/queue.DEFER).read_text();private=(root/queue.PRIVATE).read_text()
 work='\n'.join([queue.extract(defer,'__qdf_defer_func')]+[queue.extract(private,n) for n in queue.PRIVATE_NAMES]+[queue.extract(defer,n) for n in queue.PUBLIC_NAMES[1:]])
 delayed='\n'.join(queue.delayed_destroy(peer) if n=='wlan_objmgr_peer_obj_destroy' else queue.extract(peer,n) for n in queue.QUEUE)
 bodies='\n'.join(queue.extract(pdev,n) for n in NAMES)
 # Keep non-static declarations consistent with the unchanged native definitions.
 s=PREFIX.replace('REF_ENUM',refs.ref_enum(root)).replace('WORK_TYPES',queue.TYPES).replace('\nNATIVE_WORK\n','\n'+work+'\n').replace('\nNATIVE_QUEUE\n','\n'+delayed+'\n').replace('\nNATIVE_PDEV\n','\n'+bodies+'\n')
 s=s.replace('static QDF_STATUS wlan_objmgr_pdev_vdev_detach(', 'QDF_STATUS wlan_objmgr_pdev_vdev_detach(').replace('static void wlan_objmgr_pdev_release_ref(', 'void wlan_objmgr_pdev_release_ref(')
 for body in [queue.extract(pdev,n) for n in NAMES]:assert s.count(body)==1
 return s

def mutations(source):
 return [
 ('coordinator_hold',None,'assert(wlan_objmgr_pdev_try_get_ref(p,WLAN_HDD_ID_OBJ_MGR)==QDF_STATUS_SUCCESS);','/* missing coordinator pin */','EXPECTED_PDEV_ATTACH_REFERENCE'),
 ('attach_reference','wlan_objmgr_pdev_vdev_attach','wlan_objmgr_pdev_get_ref(pdev, WLAN_OBJMGR_ID);','/* missing attach pin */','EXPECTED_PDEV_ATTACH_REFERENCE'),
 ('detach_reference','wlan_objmgr_pdev_vdev_detach','wlan_objmgr_pdev_release_ref(pdev, WLAN_OBJMGR_ID);','/* missing detach put */','EXPECTED_PDEV_DETACH_REFERENCE'),
 ('final_release','wlan_objmgr_pdev_release_ref','wlan_objmgr_pdev_obj_destroy(pdev);','(void)pdev;','EXPECTED_PDEV_FINAL_RELEASE'),
 ('reference_id_gate','wlan_objmgr_pdev_release_ref','if (!qdf_atomic_read(&pdev->pdev_objmgr.ref_id_dbg[id]))','if (false)','EXPECTED_PDEV_REFERENCE_ID_GATE'),
 ('reference_admission','wlan_objmgr_pdev_try_get_ref','if (pdev->obj_state != WLAN_OBJ_STATE_CREATED)','if (false)','EXPECTED_PDEV_REFERENCE_ADMISSION'),
 ('work_drain',None,'drain(p);','/* missing process-context drain */','EXPECTED_PDEV_WORK_DRAIN'),
 ('producer_closed',None,'closed=true;\n drain(p);','closed=false;\n drain(p);','EXPECTED_PDEV_PRODUCER_CLOSED')]

def audit(root):
 if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
 if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected native revision')
 s=fixture(root);controls={}
 with tempfile.TemporaryDirectory() as tmp:
  d=Path(tmp);c=d/'pdev.c';exe=d/'pdev';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter','-g','-fsanitize=address,undefined',str(c),'-o',str(exe)];env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
  c.write_text(s);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=30,env=env);assert out.strip()=='MISHARE_NATIVE_PDEV_QUEUE_LEASE_FIXTURE_PASS_ONLY'
  for label,name,needle,replace,marker in mutations(s):
   target=s if name is None else queue.extract(s,name);assert target.count(needle)==1,(label,target.count(needle));changed=target.replace(needle,replace,1);mutant=s.replace(target,changed,1)
   c.write_text(mutant);subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=30,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-500:]);controls[label]=True
 native={path:{'sha256':hashlib.sha256((root/path).read_bytes()).hexdigest(),'functions':{n:hashlib.sha256((queue.delayed_destroy((root/path).read_text()) if n=='wlan_objmgr_peer_obj_destroy' else queue.extract((root/path).read_text(),n)).encode()).hexdigest() for n in names}} for path,names in [(PDEV,NAMES),(queue.PEER,queue.QUEUE),(queue.DEFER,queue.PUBLIC_NAMES),(queue.PRIVATE,queue.PRIVATE_NAMES)]}
 return {'status':out.strip(),'fixture_sha256':hashlib.sha256(s.encode()).hexdigest(),'source_commit':PIN,'native_inputs':native,'native_reference_id_enum_sha256':hashlib.sha256(refs.ref_enum(root).encode()).hexdigest(),'cases':50,'negative_controls_rejected':controls,'production_kernel_changed':False,'checks':['seven unchanged native PDEV reference/attach/detach/logical-delete/free bodies and fourteen native peer queue/QDF adapter bodies','50 parent-reference sequences: one/two VDEVs, direct/queued dispatch, immediate/deferred workers, root delete before/after dispatch, optional extra reference and both final put orders, plus two cancel/resubmit cases','a native PDEV reference held by the fixture caller survives VDEV detach inside worker until explicit producer closure and process-context drain','native PDEV logical delete rejects new reference admission; mismatched ID release retains accounting and reports the native BUG path','actual native PDEV free invokes modeled PSOC detach, PDEV lock destruction, actual native queue deinit/QDF cancel, queue lock destruction and actual host heap free in order'], 'limitations':'Standalone parent/queue fixture, not the full 0090 WMA/DP/MLME composite. Native PDEV final component dispatcher is a guarded leaf calling original PDEV free; component destruction and PSOC detach remain modeled. Peer destructor deliberately models last-VDEV detach and frees fixture objects; real peer/VDEV creation, destructor and DP callback graph are not executed here. Linux workqueue, atomic/lock/list endpoints are deterministic models; native peer trace/PDEV trace, concurrent producers, saturation and parent PSOC lifetime remain unverified. The extra parent reference is acquired/released by this fixture caller, not a new production shutdown coordinator or guarantee against native component teardown. Original coalescing counter residue and unchecked list insertion remain; counter is never used as quiescence proof. Full 0090 remains a separate regression. Backend stays disabled; no active START/UP SSR, phone, firmware/RF or AirDrop claim.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
