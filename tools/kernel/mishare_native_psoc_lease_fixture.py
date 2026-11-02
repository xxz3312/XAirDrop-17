#!/usr/bin/env python3
"""Actions-only native PSOC references and PDEV map through heap PDEV final free."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_pdev_free_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.previous.previous.extract
function=previous.previous.previous.function
PSOC='qca-wifi-host-cmn/umac/cmn_services/obj_mgr/src/wlan_objmgr_psoc_obj.c'
NAMES=['wlan_objmgr_psoc_get_ref','wlan_objmgr_psoc_try_get_ref','wlan_objmgr_psoc_release_ref','wlan_objmgr_psoc_pdev_attach','wlan_objmgr_psoc_pdev_detach','wlan_objmgr_psoc_obj_delete']
SUPPORT=r'''
static bool p94_enabled,p94_extra,p94_reverse,p94_deleted;
static unsigned p94_destroyed,p94_detaches;
static QDF_STATUS p94_destroy(struct wlan_objmgr_psoc *s) {
 assert(!p93_heap && !p93_parent && p93_free_calls==1 && p93_deinits==1 && p93_free_step==3 && "EXPECTED_PSOC_STORAGE_THROUGH_PDEV_FREE");
 assert(p94_deleted && !s->soc_objmgr.wlan_pdev_count && !s->soc_objmgr.wlan_pdev_id_map && !s->soc_objmgr.wlan_pdev_list[0] && !s->soc_objmgr.ref_cnt.value && !s->p94_lock);
 p94_destroyed++;return QDF_STATUS_SUCCESS;
}
static void p94_lock(struct wlan_objmgr_psoc *s) {assert(!s->p94_lock);s->p94_lock=1;}
static void p94_unlock(struct wlan_objmgr_psoc *s) {assert(s->p94_lock);s->p94_lock=0;}
static void p94_print(qdf_atomic_t *p,int level) {(void)p;(void)level;}
static void p94_notify(struct wlan_objmgr_psoc *s,unsigned type) {assert(type==3 && s->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && !s->p94_lock);}
static void p94_bug(int condition) {assert(condition && "UNEXPECTED_NATIVE_PSOC_REFERENCE_BUG");}
#define wlan_psoc_obj_lock p94_lock
#define wlan_psoc_obj_unlock p94_unlock
#define wlan_objmgr_psoc_get_ref p94_get
#define wlan_objmgr_psoc_try_get_ref p94_try
#define wlan_objmgr_psoc_release_ref p94_put
#define wlan_objmgr_psoc_pdev_attach p94_attach
#define wlan_objmgr_psoc_pdev_detach p94_detach
#define wlan_objmgr_psoc_obj_delete p94_delete
#define wlan_objmgr_psoc_obj_destroy p94_destroy
#define wlan_objmgr_print_ref_ids p94_print
#define wlan_objmgr_notify_log_delete p94_notify
#define qdf_atomic_read p92_read
#define qdf_atomic_inc p92_inc
#define qdf_atomic_dec p92_dec
#define qdf_atomic_dec_and_test p92_zero
#define WLAN_PSOC_OP 3
#define WLAN_OBJMGR_BUG(x) p94_bug(x)
#pragma push_macro("obj_mgr_err")
#undef obj_mgr_err
#define obj_mgr_err ref_log
#define obj_mgr_info ref_log
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
NATIVE_PSOC
#pragma GCC diagnostic pop
#undef obj_mgr_info
#pragma pop_macro("obj_mgr_err")
#undef WLAN_OBJMGR_BUG
#undef WLAN_PSOC_OP
#undef qdf_atomic_dec_and_test
#undef qdf_atomic_dec
#undef qdf_atomic_inc
#undef qdf_atomic_read
#undef wlan_objmgr_notify_log_delete
#undef wlan_objmgr_print_ref_ids
#undef wlan_objmgr_psoc_obj_destroy
#undef wlan_objmgr_psoc_obj_delete
#undef wlan_objmgr_psoc_pdev_detach
#undef wlan_objmgr_psoc_pdev_attach
#undef wlan_objmgr_psoc_release_ref
#undef wlan_objmgr_psoc_try_get_ref
#undef wlan_objmgr_psoc_get_ref
#undef wlan_psoc_obj_unlock
#undef wlan_psoc_obj_lock
static void p94_refs(struct wlan_objmgr_psoc *s,unsigned expected,const char *marker) {
 unsigned sum=0;for(unsigned i=0;i<WLAN_REF_ID_MAX;i++){assert(s->soc_objmgr.ref_id_dbg[i].value>=0);sum+=s->soc_objmgr.ref_id_dbg[i].value;}
 if(sum!=expected || s->soc_objmgr.ref_cnt.value!=(int)sum){fprintf(stderr,"%s\n",marker);abort();}
}
static void p94_setup(struct wlan_objmgr_psoc *s,struct wlan_objmgr_pdev *p) {
 p94_enabled=true;p94_deleted=false;p94_destroyed=p94_detaches=0;memset(&s->soc_objmgr,0,sizeof(s->soc_objmgr));s->obj_state=WLAN_OBJ_STATE_CREATED;s->p94_lock=0;
 p94_get(s,WLAN_OBJMGR_ID);
 assert(!p94_try(s,REF_NATIVE_HDD));
 if(p94_extra)assert(!p94_try(s,REF_NATIVE_OSIF));
 assert(!p94_attach(s,p));
 assert(s->soc_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value==2 && "EXPECTED_PSOC_ATTACHMENT_PIN");
 assert(s->soc_objmgr.wlan_pdev_count==1 && s->soc_objmgr.wlan_pdev_id_map==1 && s->soc_objmgr.wlan_pdev_list[0]==p && p->pdev_objmgr.wlan_pdev_id==0 && "EXPECTED_PSOC_NATIVE_MAP");
}
static void p94_close(struct wlan_objmgr_psoc *s) {
 if(!p94_enabled)return;
 assert(!p94_deleted && !p94_destroyed);p94_deleted=true;assert(!p94_delete(s));
 assert(p94_try(s,WLAN_SCAN_ID)==QDF_STATUS_E_RESOURCES && "EXPECTED_PSOC_REFERENCE_ADMISSION");
}
static void p94_complete(struct wlan_objmgr_psoc *s) {
 if(p93_heap){
  assert(!p94_destroyed && !p94_detaches && s->soc_objmgr.wlan_pdev_count==1 && s->soc_objmgr.wlan_pdev_list[0]==p93_parent && s->soc_objmgr.wlan_pdev_id_map==1);
  p94_refs(s,p94_extra?3:2,"EXPECTED_PSOC_FAILED_CHILD_REFERENCE_RETAINED");return;
 }
 assert(p94_detaches==1 && !s->soc_objmgr.wlan_pdev_count && !s->soc_objmgr.wlan_pdev_id_map && !s->soc_objmgr.wlan_pdev_list[0] && !p94_destroyed);
 p94_refs(s,p94_extra?2:1,"EXPECTED_PSOC_DETACH_PUT");
 if(p94_extra && p94_reverse)p94_put(s,REF_NATIVE_OSIF);
 p94_put(s,REF_NATIVE_HDD);
 if(p94_extra && !p94_reverse){assert(!p94_destroyed);p94_put(s,REF_NATIVE_OSIF);}
 assert(p94_destroyed==1 && "EXPECTED_PSOC_FINAL_PUT");
}
static void p94_map_contract(void) {
 struct wlan_objmgr_psoc s={0};struct wlan_objmgr_pdev a={0},b={0};s.obj_state=WLAN_OBJ_STATE_CREATED;p94_get(&s,WLAN_OBJMGR_ID);b.pdev_objmgr.wlan_pdev_id=0xff;
 assert(!p94_attach(&s,&a));p94_refs(&s,2,"EXPECTED_PSOC_MAP_ATTACH_REFERENCE");
 assert(p94_attach(&s,&b)==QDF_STATUS_E_FAILURE && b.pdev_objmgr.wlan_pdev_id==0xff && s.soc_objmgr.wlan_pdev_count==1 && s.soc_objmgr.wlan_pdev_list[0]==&a);p94_refs(&s,2,"EXPECTED_PSOC_FULL_MAP_NO_PIN");
 assert(!p94_detach(&s,&a) && a.pdev_objmgr.wlan_pdev_id==0xff && !s.soc_objmgr.wlan_pdev_count && !s.soc_objmgr.wlan_pdev_id_map);p94_refs(&s,1,"EXPECTED_PSOC_MAP_DETACH_REFERENCE");
 assert(p94_detach(&s,&a)==QDF_STATUS_E_FAILURE && !s.soc_objmgr.wlan_pdev_count);p94_refs(&s,1,"EXPECTED_PSOC_INVALID_ID_NO_PUT");
}
'''

def fixture(root):
 s,exits,stubbed=previous.fixture(root);text=(root/PSOC).read_text()
 # Select the target Kbuild default, rather than the generic header fallback of 3.
 kbuild=(root/'qcacld-3.0/Kbuild').read_text();limit=int(re.search(r'^CONFIG_WLAN_MAX_PDEVS \?= (\d+)$',kbuild,re.M)[1]);assert limit==1
 decl='#define WLAN_UMAC_MAX_PDEVS 1\nstruct wlan_objmgr_psoc_objmgr {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt,psoc_id,wlan_pdev_id_map,wlan_pdev_count;struct wlan_objmgr_pdev *wlan_pdev_list[WLAN_UMAC_MAX_PDEVS];};\nstruct wlan_objmgr_psoc {int id,obj_state,p94_lock;struct wlan_objmgr_psoc_objmgr soc_objmgr;};'
 s=owner.replace_once(s,'struct wlan_objmgr_psoc { int id; };',decl)
 s=owner.replace_once(s,'static struct wlan_objmgr_psoc psoc={1};','static struct wlan_objmgr_psoc psoc={.id=1};')
 block=SUPPORT.replace('\nNATIVE_PSOC\n','\n'+'\n'.join(extract(text,n) for n in NAMES)+'\n')
 block=owner.replace_once(block,'#define wlan_psoc_obj_lock p94_lock','void p94_get(struct wlan_objmgr_psoc *,wlan_objmgr_ref_dbgid);\nvoid p94_put(struct wlan_objmgr_psoc *,wlan_objmgr_ref_dbgid);\n#define wlan_psoc_obj_lock p94_lock')
 old=function(s,'p93_psoc_detach')
 changed=owner.replace_once(old,'p93_free_step=1;return QDF_STATUS_SUCCESS;','if(p94_enabled){assert(!p94_detach(s,p));p94_detaches++;assert(!p94_destroyed);}\n p93_free_step=1;return QDF_STATUS_SUCCESS;')
 s=owner.replace_once(s,old,block+'\n'+changed)
 case=function(s,'p92_case');case=owner.replace_once(case,'p93_parent->pdev_objmgr.wlan_psoc=&psoc;','p93_parent->pdev_objmgr.wlan_psoc=&psoc;p94_setup(&psoc,p93_parent);')
 case=case[:-1]+' p94_complete(&psoc);\n}'
 s=owner.replace_once(s,function(s,'p92_case'),case)
 clean=function(s,'clean_end');s=owner.replace_once(s,clean,owner.replace_once(clean,'if(p92_enabled){assert(!p92_delete(p93_parent));','if(p92_enabled){p94_close(&psoc);assert(!p92_delete(p93_parent));'))
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned mode=0;mode<=1;mode++)for(unsigned parent_hold=0;parent_hold<2;parent_hold++)for(unsigned reverse=0;reverse<2;reverse++) {
  pid_t c=fork();assert(c>=0);if(!c){p94_extra=true;p94_reverse=reverse;p93_mode=mode;p92_case(trace,1,0,parent_hold);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==72);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==56);','assert(count==56);\n'+extra))
 main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'p92_cases();','p94_map_contract();p92_cases();'))
 for n in NAMES:assert s.count(extract(text,n))==1,n
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[('caller_pin','p94_setup','assert(!p94_try(s,REF_NATIVE_HDD));','/* omit PSOC caller pin */','EXPECTED_PSOC_STORAGE_THROUGH_PDEV_FREE'),('attachment_pin','wlan_objmgr_psoc_pdev_attach','wlan_objmgr_psoc_get_ref(psoc, WLAN_OBJMGR_ID);','/* omit attachment pin */','EXPECTED_PSOC_ATTACHMENT_PIN'),('detach_put','wlan_objmgr_psoc_pdev_detach','wlan_objmgr_psoc_release_ref(psoc, WLAN_OBJMGR_ID);','/* omit native detach put */','EXPECTED_PSOC_DETACH_PUT'),('final_put','p94_complete','p94_put(s,REF_NATIVE_HDD);','/* omit last caller put */','EXPECTED_PSOC_FINAL_PUT'),('map_identity','wlan_objmgr_psoc_pdev_attach','objmgr->wlan_pdev_list[id] = pdev;','/* omit map ownership */','EXPECTED_PSOC_NATIVE_MAP'),('reference_admission','wlan_objmgr_psoc_try_get_ref','if (psoc->obj_state != WLAN_OBJ_STATE_CREATED)','if (false)','EXPECTED_PSOC_REFERENCE_ADMISSION')]
 for label,name,needle,mutation,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {p92_case(false,1,0,false);_Exit(0);}')
  body=extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-600:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_PSOC_LEASE_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_PSOC_function_sha256']={n:hashlib.sha256(extract((root/PSOC).read_text(),n).encode()).hexdigest() for n in NAMES};r['native_PSOC_source_sha256']=hashlib.sha256((root/PSOC).read_bytes()).hexdigest()
 r['parent_PDEV_function_sha256']={n:hashlib.sha256(extract((root/previous.previous.parent.PDEV).read_text(),n).encode()).hexdigest() for n in previous.previous.NAMES+previous.NAMES}
 r['additional_composite_cases']=72;r['negative_controls_rejected']=17;r['selected_PSOC_PDEV_map_capacity']=1
 r['checks']=['six unchanged native PSOC get/try/put, PDEV attach/detach and logical delete bodies enter all 56 heap-PDEV sequences; sixteen extra PSOC OSIF-hold/release-order cases give 72 sequences','native PSOC PDEV map attachment takes OBJMGR reference; native PDEV final free calls original PSOC detach, clears slot/count/map and releases attachment reference before PDEV queue deinit and heap free','PSOC caller HDD reference remains until actual PDEV queue deinit and heap free; missing caller pin reaches native PSOC last-reference dispatcher while PDEV storage is still live and is rejected','peer/PDEV component or detach failures retain the PSOC map, attachment and caller references; valid parent async completion eventually clears map and permits explicit last caller put','one-slot target-Kbuild-default map unit covers full attachment refusal and invalid detached-ID refusal without changing references; no multi-radio configuration claim','eleven 0093 negative controls plus six PSOC caller/attach/detach/final-put/map/admission mutations rejected']
 r['limitations']='Fixture caller integration only, no production kernel changes or automatic shutdown coordinator. PSOC storage and final destroy/free remain static modeled endpoints; native PSOC create, real PSOC component teardown, PSOC peer/VDEV attachment references and actual PSOC heap free are not executed. Native PDEV create/real components and DP producer/completion graph retain 0093 model boundaries. PSOC locking/atomic operations and map capacity are fixture choices (capacity 1 from target Kbuild default, not a full target-config or multi-radio certification). Native PSOC attach does not itself gate logical deletion and native detach does not authenticate a valid slot owner; only an owned, serialized map contract is selected, not a production fix. Global late producers, platform kworker concurrency, active START/UP SSR, backend activation, phone/firmware/RF and AirDrop remain unverified. Failure children retain unfinished resources until process exit.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
