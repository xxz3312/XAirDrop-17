#!/usr/bin/env python3
"""Actions-only native heap PSOC final dispatch/free after the PDEV composite."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_psoc_lease_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
NAMES=['wlan_objmgr_psoc_object_status','wlan_objmgr_psoc_component_obj_detach','wlan_objmgr_psoc_obj_destroy','wlan_objmgr_psoc_obj_free','wlan_objmgr_psoc_peer_list_deinit']
SUPPORT=r'''
static void p94_lock(struct wlan_objmgr_psoc *);
static void p94_unlock(struct wlan_objmgr_psoc *);
typedef QDF_STATUS (*wlan_objmgr_psoc_destroy_handler)(struct wlan_objmgr_psoc *,void *);
static struct {wlan_objmgr_psoc_destroy_handler psoc_destroy_handler[WLAN_UMAC_MAX_COMPONENTS];void *psoc_destroy_handler_arg[WLAN_UMAC_MAX_COMPONENTS];} p95_registry;
static unsigned p95_mode,p95_heap,p95_order,p95_free_step,p95_lists,p95_free_calls,p95_bugs;
static bool p95_global_live;
static void *p95_async;
static int p95_bad;
static QDF_STATUS p95_result;
QDF_STATUS p95_component_detach(struct wlan_objmgr_psoc *,enum wlan_umac_comp_id,void *);
static QDF_STATUS p95_free_gate(struct wlan_objmgr_psoc *);
static void p95_bug(int condition) {assert(!condition && p95_mode==2);p95_bugs++;}
static void p95_notify(struct wlan_objmgr_psoc *s,unsigned kind) {assert(kind==3 && s==p95_active && p95_heap==1 && p94_destroyed==1 && !s->soc_objmgr.ref_cnt.value && !s->p94_lock && !p93_heap && !p93_parent);}
static void p95_print(struct wlan_objmgr_psoc *s) {assert(s==p95_active);}
static void p95_dump(void *p,size_t n,struct wlan_objmgr_psoc *s,unsigned kind,const char *name) {
 assert(s==p95_active);
 if(kind==403)assert(p==s && n==sizeof(*s) && !strcmp(name,"wlan_objmgr_psoc"));
 else assert(kind==404 && p==&p95_registry && n==sizeof(p95_registry) && !strcmp(name,"wlan_objmgr_global"));
}
static QDF_STATUS p95_global_detach(struct wlan_objmgr_psoc *s) {
 assert(s==p95_active && p95_global_live && p95_order==2 && !p95_free_step && !s->soc_objmgr.wlan_pdev_count && !s->soc_objmgr.wlan_pdev_id_map);
 if(p95_mode==3)return QDF_STATUS_E_FAILURE;
 p95_global_live=false;p95_free_step=1;return QDF_STATUS_SUCCESS;
}
static void p95_lock_destroy(int *lock) {
 assert(p95_active);
 if(lock==&p95_active->soc_objmgr.peer_list.peer_list_lock){assert(*lock==1 && p95_free_step==1 && "EXPECTED_PSOC_GLOBAL_DETACH_BEFORE_HASH_LOCK");*lock=0;p95_free_step=2;return;}
 assert(lock==&p95_active->psoc_lock && *lock==1 && p95_free_step==2 && p95_lists==WLAN_PEER_HASHSIZE && "EXPECTED_PSOC_HASHES_BEFORE_FINAL_LOCK");*lock=0;p95_free_step=3;
}
static void p95_list_destroy(struct p95_hash_list *list) {
 struct p95_hash_list *base=p95_active->soc_objmgr.peer_list.peer_hash;
 assert(!p95_active->soc_objmgr.peer_list.peer_list_lock && p95_free_step==2 && "EXPECTED_PSOC_HASH_LOCK_BEFORE_LISTS");
 assert(list==&base[p95_lists] && list->live && !list->count && "EXPECTED_PSOC_ORDERED_EMPTY_HASHES");list->live=false;p95_lists++;
}
static void p95_storage_free(struct wlan_objmgr_psoc *s) {
 assert(s==p95_active && p95_heap==1 && !p95_global_live && p95_free_step==3 && p95_lists==WLAN_PEER_HASHSIZE && !s->psoc_lock && !s->soc_objmgr.peer_list.peer_list_lock && "EXPECTED_PSOC_LOCKS_BEFORE_HEAP_FREE");
 assert(!s->soc_objmgr.ref_cnt.value && !p93_heap && !p93_parent && !objects_live && !p89_heap);
 p95_heap--;p95_free_calls++;p95_active=NULL;free(s);
}
#define wlan_psoc_obj_lock p94_lock
#define wlan_psoc_obj_unlock p94_unlock
#define wlan_objmgr_psoc_object_status p95_status
#define wlan_objmgr_psoc_component_obj_detach p95_component_detach
#define wlan_objmgr_psoc_obj_destroy p95_native_destroy
#define wlan_objmgr_psoc_obj_free p95_native_free
#define wlan_objmgr_psoc_peer_list_deinit p95_hash_deinit
#define wlan_objmgr_psoc_object_detach p95_global_detach
#define qdf_spinlock_destroy p95_lock_destroy
#define qdf_list_destroy p95_list_destroy
#define qdf_mem_free p95_storage_free
#define g_umac_glb_obj (&p95_registry)
#define wlan_objmgr_notify_destroy p95_notify
#define wlan_print_psoc_info p95_print
#define wlan_minidump_remove p95_dump
#define WLAN_PSOC_OP 3
#define WLAN_MD_OBJMGR_PSOC 403
#define WLAN_MD_OBJMGR_GLOBAL 404
#pragma push_macro("obj_mgr_err")
#undef obj_mgr_err
#define obj_mgr_err ref_log
#define obj_mgr_info ref_log
#pragma push_macro("QDF_BUG")
#undef QDF_BUG
#define QDF_BUG(x) p95_bug(x)
#define WLAN_OBJMGR_BUG(x) p95_bug(x)
NATIVE_HASH_DEINIT
NATIVE_PSOC_FREE
#undef wlan_objmgr_psoc_obj_free
#define wlan_objmgr_psoc_obj_free p95_free_gate
NATIVE_PSOC_COMPONENTS
#undef WLAN_OBJMGR_BUG
#pragma pop_macro("QDF_BUG")
#undef obj_mgr_info
#pragma pop_macro("obj_mgr_err")
#undef WLAN_MD_OBJMGR_GLOBAL
#undef WLAN_MD_OBJMGR_PSOC
#undef WLAN_PSOC_OP
#undef wlan_minidump_remove
#undef wlan_print_psoc_info
#undef wlan_objmgr_notify_destroy
#undef g_umac_glb_obj
#undef qdf_mem_free
#undef qdf_list_destroy
#undef qdf_spinlock_destroy
#undef wlan_objmgr_psoc_object_detach
#undef wlan_objmgr_psoc_peer_list_deinit
#undef wlan_objmgr_psoc_obj_free
#undef wlan_objmgr_psoc_obj_destroy
#undef wlan_objmgr_psoc_component_obj_detach
#undef wlan_objmgr_psoc_object_status
#undef wlan_psoc_obj_unlock
#undef wlan_psoc_obj_lock
static QDF_STATUS p95_free_gate(struct wlan_objmgr_psoc *s) {
 assert(!p95_async && "EXPECTED_PSOC_ASYNC_COMPONENT_WAIT");
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)assert(!s->soc_comp_priv_obj[i] && s->obj_status[i]!=QDF_STATUS_E_FAILURE && "EXPECTED_PSOC_COMPONENT_SUCCESS");
 return p95_native_free(s);
}
static QDF_STATUS p95_low(struct wlan_objmgr_psoc *s,void *arg) {
 assert(s==p95_active && arg==&p95_registry && !p95_order && "EXPECTED_PSOC_FORWARD_COMPONENT_ORDER");p95_order=1;
 void *token=s->soc_comp_priv_obj[0];assert(token && !p95_component_detach(s,0,token));free(token);return QDF_STATUS_SUCCESS;
}
static QDF_STATUS p95_high(struct wlan_objmgr_psoc *s,void *arg) {
 assert(s==p95_active && arg==&p95_registry && p95_order==1 && "EXPECTED_PSOC_FORWARD_COMPONENT_ORDER");p95_order=2;
 unsigned id=WLAN_UMAC_COMP_ID_MAX-1;void *token=s->soc_comp_priv_obj[id];assert(token);
 if(p95_mode==2)return QDF_STATUS_E_FAILURE;
 if(p95_mode==1 || p95_mode==4){p95_async=token;s->soc_comp_priv_obj[id]=NULL;return QDF_STATUS_COMP_ASYNC;}
 assert(!p95_component_detach(s,id,token));free(token);return QDF_STATUS_SUCCESS;
}
static void p95_arm(struct wlan_objmgr_psoc *s) {
 memset(&p95_registry,0,sizeof(p95_registry));
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)s->obj_status[i]=QDF_STATUS_COMP_DISABLED;
 unsigned ids[]={0,WLAN_UMAC_COMP_ID_MAX-1};
 for(unsigned i=0;i<2;i++){unsigned id=ids[i];s->soc_comp_priv_obj[id]=malloc(1);assert(s->soc_comp_priv_obj[id]);s->obj_status[id]=QDF_STATUS_SUCCESS;p95_registry.psoc_destroy_handler[id]=i?p95_high:p95_low;p95_registry.psoc_destroy_handler_arg[id]=&p95_registry;}
}
static void p95_allocate(void) {
 assert(!p95_heap);p95_active=calloc(1,sizeof(*p95_active));assert(p95_active);p95_active->id=1;p95_active->psoc_lock=1;p95_heap=1;p95_global_live=true;p95_order=p95_free_step=p95_lists=p95_free_calls=p95_bugs=0;p95_async=NULL;
}
static void p95_hash_setup(struct wlan_objmgr_psoc *s) {
 s->soc_objmgr.peer_list.peer_list_lock=1;
 for(unsigned i=0;i<WLAN_PEER_HASHSIZE;i++){s->soc_objmgr.peer_list.peer_hash[i].live=true;s->soc_objmgr.peer_list.peer_hash[i].count=0;}
}
static void p95_completed(void) {
 if(!p94_destroyed){assert(p95_heap==1 && p95_active && p93_heap && p95_global_live && !p95_free_calls);return;}
 if(p95_mode==1 || p95_mode==4){
  struct wlan_objmgr_psoc *s=p95_active;assert(s && p95_heap==1 && p95_result==QDF_STATUS_COMP_ASYNC && s->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && p95_async && p95_global_live && !p95_free_step && !p95_lists);
  if(p95_mode==4){assert(p95_component_detach(s,WLAN_UMAC_COMP_ID_MAX-1,&p95_bad)==QDF_STATUS_E_FAILURE && "EXPECTED_PSOC_BAD_ASYNC_TOKEN");assert(p95_active==s && p95_heap==1 && p95_async && p95_global_live && !p95_free_calls && s->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED);return;}
  void *token=p95_async;p95_async=NULL;free(token);assert(!p95_component_detach(s,WLAN_UMAC_COMP_ID_MAX-1,NULL));
 }
 if(p95_mode==2){assert(p95_result==QDF_STATUS_E_FAILURE && p95_bugs==1 && p95_heap==1 && p95_active && p95_active->soc_comp_priv_obj[WLAN_UMAC_COMP_ID_MAX-1] && p95_global_live && !p95_free_step && !p95_free_calls);return;}
 if(p95_mode==3){assert(p95_result==QDF_STATUS_E_FAILURE && p95_heap==1 && p95_active && p95_global_live && !p95_free_step && !p95_lists && p95_active->psoc_lock==1 && p95_active->soc_objmgr.peer_list.peer_list_lock==1);return;}
 assert(!p95_heap && !p95_active && !p95_global_live && p95_free_calls==1 && p95_lists==WLAN_PEER_HASHSIZE && p95_free_step==3 && "EXPECTED_PSOC_ACTUAL_HEAP_FREE");
}
'''

def fixture(root):
 s,exits,stubbed=previous.fixture(root);native=(root/previous.PSOC).read_text();header=(root/'qca-wifi-host-cmn/umac/cmn_services/obj_mgr/inc/wlan_objmgr_cmn.h').read_text();hashsize=int(re.search(r'^#define WLAN_PEER_HASHSIZE (\d+)$',header,re.M)[1]);assert hashsize==64
 s=owner.replace_once(s,'#define WLAN_UMAC_MAX_PDEVS 1','#define WLAN_PEER_HASHSIZE 64\nstruct p95_hash_list {bool live;unsigned count;};\nstruct wlan_peer_list {int peer_list_lock;struct p95_hash_list peer_hash[WLAN_PEER_HASHSIZE];};\n#define WLAN_UMAC_MAX_PDEVS 1')
 s=owner.replace_once(s,'struct wlan_objmgr_pdev *wlan_pdev_list[WLAN_UMAC_MAX_PDEVS];','struct wlan_objmgr_pdev *wlan_pdev_list[WLAN_UMAC_MAX_PDEVS];struct wlan_peer_list peer_list;')
 s=owner.replace_once(s,'struct wlan_objmgr_psoc {int id,obj_state,p94_lock;struct wlan_objmgr_psoc_objmgr soc_objmgr;};','struct wlan_objmgr_psoc {int id,obj_state,p94_lock,psoc_lock;struct wlan_objmgr_psoc_objmgr soc_objmgr;void *soc_comp_priv_obj[WLAN_UMAC_MAX_COMPONENTS];QDF_STATUS obj_status[WLAN_UMAC_MAX_COMPONENTS];};\nstatic struct wlan_objmgr_psoc p95_default;\nstatic struct wlan_objmgr_psoc *p95_active=&p95_default;')
 block=SUPPORT.replace('\nNATIVE_HASH_DEINIT\n','\n'+extract(native,NAMES[-1])+'\n').replace('\nNATIVE_PSOC_FREE\n','\n'+extract(native,'wlan_objmgr_psoc_obj_free')+'\n').replace('\nNATIVE_PSOC_COMPONENTS\n','\n'+'\n'.join(extract(native,n) for n in NAMES[:3])+'\n')
 destroy=function(s,'p94_destroy');s=owner.replace_once(s,destroy,block+'\n'+owner.replace_once(destroy,'p94_destroyed++;return QDF_STATUS_SUCCESS;','p94_destroyed++;p95_arm(s);p95_result=p95_native_destroy(s);return p95_result;'))
 case=function(s,'p92_case');case=owner.replace_once(case,'assert(!p93_heap);','p95_allocate();assert(!p93_heap);');case=owner.replace_once(case,'p94_setup(&psoc,p93_parent);','p94_setup(&psoc,p93_parent);p95_hash_setup(p95_active);');case=owner.replace_once(case,'p94_complete(&psoc);','p94_complete(&psoc);q90_atomic=false;p95_completed();');s=owner.replace_once(s,function(s,'p92_case'),case)
 s=owner.replace_once(s,'static struct wlan_objmgr_psoc psoc={.id=1};','static struct wlan_objmgr_psoc p95_default={.id=1};')
 s=owner.replace_once(s,'static struct wlan_objmgr_pdev p93_default={.psoc=&psoc};','static struct wlan_objmgr_pdev p93_default={.psoc=&p95_default};')
 s=re.sub(r'\bpsoc\.', 'p95_active->',s);s=re.sub(r'&psoc\b(?!->)', 'p95_active',s)
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned mode=1;mode<=4;mode++)for(unsigned hold=0;hold<2;hold++) {
  pid_t c=fork();assert(c>=0);if(!c){p95_mode=mode;p94_extra=hold;p92_case(trace,1,0,false);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==88);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==72);','assert(count==72);\n'+extra))
 for n in previous.NAMES+NAMES:assert s.count(extract(native,n))==1,n
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[('global_detach','wlan_objmgr_psoc_obj_free','wlan_objmgr_psoc_object_detach(psoc)','QDF_STATUS_SUCCESS','EXPECTED_PSOC_GLOBAL_DETACH_BEFORE_HASH_LOCK',0),('hash_deinit','wlan_objmgr_psoc_obj_free','wlan_objmgr_psoc_peer_list_deinit(&psoc->soc_objmgr.peer_list);','/* omit peer hash deinit */','EXPECTED_PSOC_HASHES_BEFORE_FINAL_LOCK',0),('hash_lock','wlan_objmgr_psoc_peer_list_deinit','qdf_spinlock_destroy(&peer_list->peer_list_lock);','/* omit peer hash lock destroy */','EXPECTED_PSOC_HASH_LOCK_BEFORE_LISTS',0),('all_hashes','wlan_objmgr_psoc_peer_list_deinit','i < WLAN_PEER_HASHSIZE','i < WLAN_PEER_HASHSIZE - 1','EXPECTED_PSOC_HASHES_BEFORE_FINAL_LOCK',0),('final_lock','wlan_objmgr_psoc_obj_free','qdf_spinlock_destroy(&psoc->psoc_lock);','/* omit final PSOC lock */','EXPECTED_PSOC_LOCKS_BEFORE_HEAP_FREE',0),('heap_free','wlan_objmgr_psoc_obj_free','qdf_mem_free(psoc);','/* omit actual PSOC free */','EXPECTED_PSOC_ACTUAL_HEAP_FREE',0),('component_order','wlan_objmgr_psoc_obj_destroy','for (id = 0; id < WLAN_UMAC_MAX_COMPONENTS; id++)','for (id = WLAN_UMAC_MAX_COMPONENTS; id-- > 0;)','EXPECTED_PSOC_FORWARD_COMPONENT_ORDER',0),('async_wait','wlan_objmgr_psoc_obj_destroy','if (obj_status == QDF_STATUS_COMP_ASYNC)','if (false)','EXPECTED_PSOC_ASYNC_COMPONENT_WAIT',1),('component_success','wlan_objmgr_psoc_obj_destroy','if (obj_status == QDF_STATUS_E_FAILURE)','if (false)','EXPECTED_PSOC_COMPONENT_SUCCESS',2)]
 for label,name,needle,mutation,marker,mode in controls:
  target=owner.replace_once(source,function(source,'main'),f'int main(void) {{p95_mode={mode};p92_case(false,1,0,false);_Exit(0);}}');body=extract(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-600:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_PSOC_FREE_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_PSOC_function_sha256']={n:hashlib.sha256(extract((root/previous.PSOC).read_text(),n).encode()).hexdigest() for n in previous.NAMES+NAMES};r['native_PSOC_source_sha256']=hashlib.sha256((root/previous.PSOC).read_bytes()).hexdigest()
 r['parent_PDEV_function_sha256']={n:hashlib.sha256(extract((root/previous.previous.previous.parent.PDEV).read_text(),n).encode()).hexdigest() for n in previous.previous.previous.NAMES+previous.previous.NAMES}
 r['additional_composite_cases']=88;r['negative_controls_rejected']=26;r['native_peer_hash_buckets']=64;r['selected_PSOC_PDEV_map_capacity']=1;r['native_peer_hash_header_sha256']=hashlib.sha256((root/'qca-wifi-host-cmn/umac/cmn_services/obj_mgr/inc/wlan_objmgr_cmn.h').read_bytes()).hexdigest()
 r['checks']=['all 72 prior reference/PDEV-map sequences now use heap PSOC storage; sixteen added PSOC asynchronous/component/global-detach/invalid-completion cases give 88 combinations','original PSOC status, component detach, forward final dispatcher, peer-list deinit and final free run after actual PDEV heap release','native PSOC free invokes modeled global detach, native peer-list deinit with all 64 empty modeled lists and its modeled lock destruction, final PSOC lock destruction, then actual host heap free','valid native asynchronous component detach resumes final free in fixture process context; component failure/global detach failure and bad async token preserve the unfinished resources','seventeen prior and nine new final-dispatch/free mutation controls rejected; baseline retains static fallback parents']
 r['limitations']='Fixture caller integration only, no production shutdown coordinator. PSOC/PDEV allocation and initialization, component registry/two sentinel handlers, global PSOC registration/detach, peer hash lists, atomics and locks remain deterministic models. Native PSOC/PDEV create, actual PSOC peer/VDEV reference graph, real component implementations, real DP unmap/completion callbacks, Linux kworker concurrency and late producers are not executed. Empty hash buckets are set up by fixture, not native peer list init. Failure children intentionally retain unfinished resources until process exit; QDF_BUG is a controlled model endpoint. Only private qualified parent-shutdown sequences are selected; no shared live PSOC teardown authority, native attach/detach hardening, active START/UP SSR, backend activation, phone/firmware/RF or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
