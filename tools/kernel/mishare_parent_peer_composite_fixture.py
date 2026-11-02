#!/usr/bin/env python3
"""Actions-only native PDEV reference/attachment in the 0090 peer/VDEV composite."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import mishare_native_peer_queue_fixture as previous
import mishare_native_pdev_queue_fixture as parent
owner=previous.owner
engine=previous.engine
NAMES=parent.NAMES[:-1]
SUPPORT=r'''
static bool p92_enabled,p92_closed,p92_extra;
static unsigned p92_destroyed,p92_attaches,p92_detaches;
static QDF_STATUS p92_destroy(struct wlan_objmgr_pdev *);
static void p92_get(struct wlan_objmgr_pdev *,wlan_objmgr_ref_dbgid);
static void p92_put(struct wlan_objmgr_pdev *,wlan_objmgr_ref_dbgid);
static void p92_inc(qdf_atomic_t *n) {n->value++;}
static void p92_dec(qdf_atomic_t *n) {assert(n->value>0);n->value--;}
static bool p92_zero(qdf_atomic_t *n) {assert(n->value>0);return !--n->value;}
static int p92_read(qdf_atomic_t *n) {return n->value;}
static void p92_lock(struct wlan_objmgr_pdev *p) {assert(!p->p92_lock);p->p92_lock=1;}
static void p92_unlock(struct wlan_objmgr_pdev *p) {assert(p->p92_lock);p->p92_lock=0;}
static unsigned p92_id(struct wlan_objmgr_pdev *p) {(void)p;return 0;}
static void p92_refs(qdf_atomic_t *p,int level) {(void)p;(void)level;}
static void p92_notify(struct wlan_objmgr_pdev *p,unsigned kind) {assert(kind==1 && p->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED);}
static void p92_add(struct wlan_objmgr_vdev **head,struct wlan_objmgr_vdev *v) {assert(!*head);*head=v;}
static void p92_remove(struct wlan_objmgr_vdev **head,struct wlan_objmgr_vdev *v) {assert(*head==v);*head=NULL;}
static void p92_check(struct wlan_objmgr_pdev *p,unsigned expected,const char *marker) {
 unsigned sum=0;for(unsigned i=0;i<WLAN_REF_ID_MAX;i++){assert(p->pdev_objmgr.ref_id_dbg[i].value>=0);sum+=p->pdev_objmgr.ref_id_dbg[i].value;}
 if(sum!=expected || p->pdev_objmgr.ref_cnt.value!=(int)sum){fprintf(stderr,"%s\n",marker);abort();}
}
#define wlan_objmgr_pdev_get_ref p92_get
#define wlan_objmgr_pdev_try_get_ref p92_try
#define wlan_objmgr_pdev_release_ref p92_put
#define wlan_objmgr_pdev_vdev_attach p92_attach
#define wlan_objmgr_pdev_vdev_detach p92_detach
#define wlan_objmgr_pdev_obj_delete p92_delete
#define wlan_objmgr_pdev_obj_destroy p92_destroy
#define wlan_objmgr_pdev_get_pdev_id p92_id
#define wlan_objmgr_print_ref_ids p92_refs
#define wlan_objmgr_notify_log_delete p92_notify
#define wlan_pdev_obj_lock p92_lock
#define wlan_pdev_obj_unlock p92_unlock
#define wlan_obj_pdev_vdevlist_add_tail p92_add
#define wlan_obj_pdev_vdevlist_remove_vdev p92_remove
#define qdf_atomic_inc p92_inc
#define qdf_atomic_dec p92_dec
#define qdf_atomic_dec_and_test p92_zero
#define qdf_atomic_read p92_read
#define WLAN_PDEV_OP 1
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
NATIVE_PARENT
#pragma GCC diagnostic pop
#undef WLAN_PDEV_OP
#undef qdf_atomic_read
#undef qdf_atomic_dec_and_test
#undef qdf_atomic_dec
#undef qdf_atomic_inc
#undef wlan_obj_pdev_vdevlist_remove_vdev
#undef wlan_obj_pdev_vdevlist_add_tail
#undef wlan_pdev_obj_unlock
#undef wlan_pdev_obj_lock
#undef wlan_objmgr_notify_log_delete
#undef wlan_objmgr_print_ref_ids
#undef wlan_objmgr_pdev_get_pdev_id
#undef wlan_objmgr_pdev_obj_destroy
#undef wlan_objmgr_pdev_obj_delete
#undef wlan_objmgr_pdev_vdev_detach
#undef wlan_objmgr_pdev_vdev_attach
#undef wlan_objmgr_pdev_release_ref
#undef wlan_objmgr_pdev_try_get_ref
#undef wlan_objmgr_pdev_get_ref
static QDF_STATUS p92_destroy(struct wlan_objmgr_pdev *p) {
 assert(!p->peer_obj_free_work.work.running && "EXPECTED_COMPOSITE_NO_WORKER_PARENT_RELEASE");
 assert(p92_closed && "EXPECTED_COMPOSITE_PRODUCER_CLOSED");
 assert(!p->peer_obj_free_work.work.pending && !p->peer_free_list.count && !p->q90_live && "EXPECTED_COMPOSITE_PARENT_DRAIN");
 assert(!p->pdev_objmgr.wlan_vdev_count && !p->pdev_objmgr.wlan_vdev_list && !objects_live && !p89_heap && !p->p89_peer_count && "EXPECTED_COMPOSITE_PARENT_CHILDREN_GONE");
 p92_check(p,0,"EXPECTED_COMPOSITE_FINAL_ACCOUNTING");p92_destroyed++;return 0;
}
static void p92_begin(struct wlan_objmgr_pdev *p,bool extra) {
 assert(!objects_live && !p89_heap);memset(&p->pdev_objmgr,0,sizeof(p->pdev_objmgr));p->obj_state=WLAN_OBJ_STATE_CREATED;p->pdev_objmgr.max_vdev_count=1;p92_extra=extra;p92_closed=false;p92_destroyed=p92_attaches=p92_detaches=0;
 p92_get(p,WLAN_OBJMGR_ID);
 assert(!p92_try(p,REF_NATIVE_HDD));
 if(extra)assert(!p92_try(p,REF_NATIVE_OSIF));
 p92_check(p,extra?3:2,"EXPECTED_COMPOSITE_CALLER_PIN");
}
static void p92_finish(struct wlan_objmgr_pdev *p) {
 if(!p92_enabled)return;
 p92_closed=true;
 assert(!p->q90_live && !p->peer_free_list.count && !p->peer_obj_free_work.work.pending && !p->peer_obj_free_work.work.running && "EXPECTED_COMPOSITE_PARENT_DRAIN");
 p92_check(p,p92_extra?2:1,"EXPECTED_COMPOSITE_PARENT_DETACH_PUT");
 assert(p92_attaches==1 && p92_detaches==1 && !p92_destroyed && "EXPECTED_COMPOSITE_NATIVE_ATTACHMENT");
 p92_put(p,REF_NATIVE_HDD);
 if(p92_extra){assert(!p92_destroyed);p92_put(p,REF_NATIVE_OSIF);}
 assert(p92_destroyed==1 && "EXPECTED_COMPOSITE_FINAL_PUT");
}
'''
LATE=r'''
static void p92_case(bool trace,unsigned mode,unsigned peer_mode,bool extra) {
 p92_enabled=true;ref_trace_mode=trace;q90_mode=mode;q90_atomic=mode!=4;q90_inline_worker=mode==6;p89_mode=peer_mode;
 p92_begin(&pdev,extra);engine_cycle(5240,false,0);
 if(peer_mode>=2 && peer_mode<=5) {
  assert(!p92_destroyed && objects_live && p89_heap && pdev.pdev_objmgr.wlan_vdev_count==1 && !p92_detaches && "EXPECTED_COMPOSITE_FAILURE_RETAINS_PARENT");
  p92_check(&pdev,extra?3:2,"EXPECTED_COMPOSITE_FAILURE_PARENT_REFS");
 }else assert(p92_destroyed==1 && !objects_live && !p89_heap);
}
static void p92_cases(void) {
 unsigned count=0;
 for(unsigned trace=0;trace<2;trace++)for(unsigned mode=1;mode<=6;mode+=mode==1?3:1)for(unsigned peer=0;peer<2;peer++)for(unsigned extra=0;extra<2;extra++) {
  pid_t c=fork();assert(c>=0);if(!c){p92_case(trace,mode,peer,extra);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==32);
 for(unsigned trace=0;trace<2;trace++)for(unsigned peer=2;peer<=5;peer++) {
  pid_t c=fork();assert(c>=0);if(!c){p92_case(trace,1,peer,true);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==40);
}
'''

def fixture(root):
 s,exits,stubbed=previous.fixture(root)
 s=owner.replace_once(s,'struct wlan_objmgr_pdev {', 'struct wlan_objmgr_pdev_objmgr {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt,wlan_vdev_count,max_vdev_count;struct wlan_objmgr_vdev *wlan_vdev_list;};\nstruct wlan_objmgr_pdev {struct wlan_objmgr_pdev_objmgr pdev_objmgr;int obj_state,p92_lock;')
 old=previous.function(s,'wlan_objmgr_pdev_vdev_detach')
 block=SUPPORT.replace('NATIVE_PARENT','\n'.join(previous.extract((root/parent.PDEV).read_text(),n) for n in NAMES))
 # Preserve static declarations while original bodies remain unchanged behind macro names.
 block=block.replace('static void p92_get(', 'void p92_get(').replace('static void p92_put(', 'void p92_put(')
 s=owner.replace_once(s,old,block+'\n'+old.replace('detach_calls++;','detach_calls++;if(p92_enabled){if(detach_fail)return QDF_STATUS_E_FAILURE;p92_detaches++;return p92_detach(p,v);}'))
 s=owner.replace_once(s,'v->pdev=p;v->mode=17;','v->pdev=p;if(p92_enabled){assert(!p92_attach(p,v));p92_attaches++;p92_check(p,p92_extra?4:3,"EXPECTED_COMPOSITE_ATTACH_PIN");}v->mode=17;')
 clean=previous.function(s,'clean_end')
 s=owner.replace_once(s,clean,owner.replace_once(clean,'clean_active=true;','if(p92_enabled){assert(!p92_delete(&pdev));assert(p92_try(&pdev,WLAN_SCAN_ID)==QDF_STATUS_E_RESOURCES && "EXPECTED_COMPOSITE_PARENT_ADMISSION");}\n clean_active=true;'))
 shutdown=previous.function(s,'q90_shutdown')
 s=owner.replace_once(s,shutdown,shutdown.replace('q90_atomic=old;','p92_finish(&pdev);q90_atomic=old;'))
 main=previous.function(s,'main');s=owner.replace_once(s,main,LATE+'\n'+owner.replace_once(main,'q90_contracts();','p92_cases();q90_contracts();'))
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 # The full 0090 negatives continue in their independent CI regression.
 exe=directory/'engine'
 controls=[('caller_pin','p92_begin','assert(!p92_try(p,REF_NATIVE_HDD));','/* missing caller hold */','EXPECTED_COMPOSITE_CALLER_PIN'),('attachment_pin','wlan_objmgr_pdev_vdev_attach','wlan_objmgr_pdev_get_ref(pdev, WLAN_OBJMGR_ID);','/* missing native attach hold */','EXPECTED_COMPOSITE_ATTACH_PIN'),('attachment_put','wlan_objmgr_pdev_vdev_detach','wlan_objmgr_pdev_release_ref(pdev, WLAN_OBJMGR_ID);','/* missing native detach put */','EXPECTED_COMPOSITE_PARENT_DETACH_PUT'),('final_put','p92_finish','p92_put(p,REF_NATIVE_HDD);','/* missing final caller put */','EXPECTED_COMPOSITE_FINAL_PUT'),('parent_admission','wlan_objmgr_pdev_try_get_ref','if (pdev->obj_state != WLAN_OBJ_STATE_CREATED)','if (false)','EXPECTED_COMPOSITE_PARENT_ADMISSION')]
 for label,name,needle,replacement,marker in controls:
  target=owner.replace_once(source,previous.function(source,'main'),'int main(void) {p92_case(false,1,0,false);_Exit(0);}')
  body=previous.extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,replacement)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-600:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_PARENT_PEER_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_PDEV_function_sha256']={n:hashlib.sha256(previous.extract((root/parent.PDEV).read_text(),n).encode()).hexdigest() for n in NAMES}
 r['additional_composite_cases']=40;r['new_negative_controls_rejected']=['caller_pin','attachment_pin','attachment_put','final_put','parent_admission']
 r['checks']=['0090 baseline retained; 32 native PDEV/peer/VDEV sequences plus eight retained-failure cases under both VDEV trace modes','native PDEV attachment called from modeled VDEV allocator; actual native VDEV final-free calls native PDEV detach through fixture wrapper','full existing native peer worker/component/free, VDEV reference/component/free and native SM chain executes; PDEV caller pin remains until VDEV storage gone and queue deinit complete','native PDEV logical delete rejects new references; parent final zero reached only after explicit caller put; extra parent reference postpones final endpoint']
 r['limitations']='Fixture caller integration only; no production kernel changes or automatic shutdown coordinator. PDEV and PSOC storage remain static harness objects; final PDEV component dispatcher/free is a guarded model, not native PDEV free or heap deallocation. Parent VDEV list is a one-entry model. VDEV creation, peer DP-unmap producer, DP completion gating, PSOC/list operations, workqueue and platform primitives retain 0090 model boundaries. Only the selected added cases enable native PDEV attachment; other 0090 cases remain unchanged. Failure cases retain resources until child process exit. No concurrent late producer, PSOC lifetime, peer trace parity, active START/UP SSR recovery, backend activation, phone/firmware/RF or AirDrop proof.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
