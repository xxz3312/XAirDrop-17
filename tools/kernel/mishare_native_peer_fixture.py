#!/usr/bin/env python3
"""Actions-only native self-peer destruction and VDEV peer detach composite."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_refs_fixture as previous
from mishare_recovery_fixture import function
owner=previous.owner
engine=previous.engine
PEER='qca-wifi-host-cmn/umac/cmn_services/obj_mgr/src/wlan_objmgr_peer_obj.c'
VDEV=previous.OBJECT
COMMON=previous.previous.COMMON
NAMES=['wlan_objmgr_peer_object_status','wlan_objmgr_peer_obj_free','wlan_objmgr_peer_component_obj_detach','__wlan_objmgr_peer_obj_destroy','wlan_objmgr_peer_get_debug_id_ref','wlan_objmgr_peer_release_debug_id_ref','wlan_objmgr_peer_get_ref','wlan_objmgr_peer_try_get_ref','wlan_objmgr_peer_release_ref','wlan_objmgr_peer_obj_delete']
STRUCT=r'''
struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;WLAN_OBJ_STATE obj_state;int peer_lock;struct {enum wlan_peer_type peer_type;} peer_mlme;struct {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt;} peer_objmgr;QDF_STATUS obj_status[WLAN_UMAC_MAX_COMPONENTS];void *peer_comp_priv_obj[WLAN_UMAC_MAX_COMPONENTS];u8 mac[6];};
'''
SUPPORT=r'''
#define QDF_STATUS_COMP_ASYNC 101
#define QDF_STATUS_MAXCOMP_FAIL 102
#define WLAN_PEER_OP 3
#define WLAN_MD_OBJMGR_PEER 203
#define QDF_MAC_ADDR_FMT "%p"
#define QDF_MAC_ADDR_REF(p) ((void *)(p))
static unsigned p89_mode,p89_order,p89_destroy_calls,p89_free_calls,p89_heap,p89_parent_gets,p89_parent_puts,p89_psoc_detaches,p89_vdev_detaches,p89_bugs,p89_notify_freed;
static bool p89_bss,p89_vdev_link,p89_psoc_link;
static int p89_parent_before,p89_bad;
static void *p89_async;
static QDF_STATUS p89_result;
typedef QDF_STATUS (*wlan_objmgr_peer_destroy_handler)(struct wlan_objmgr_peer *,void *);
static struct {wlan_objmgr_peer_destroy_handler peer_destroy_handler[WLAN_UMAC_MAX_COMPONENTS];void *peer_destroy_handler_arg[WLAN_UMAC_MAX_COMPONENTS];} p89_registry,*p89_handlers=&p89_registry;
static QDF_STATUS p89_physical_free(struct wlan_objmgr_peer *);
static QDF_STATUS p89_vdev_detach(struct wlan_objmgr_vdev *,struct wlan_objmgr_peer *);
static void p89_bug(int condition) {assert(!condition && p89_mode==2 && "UNEXPECTED_NATIVE_PEER_BUG");p89_bugs++;}
static void p89_log(const char *fmt,...) {(void)fmt;}
static void wlan_peer_obj_lock(struct wlan_objmgr_peer *p) {assert(p && !p->peer_lock);p->peer_lock=1;}
static void wlan_peer_obj_unlock(struct wlan_objmgr_peer *p) {assert(p && p->peer_lock);p->peer_lock=0;}
static u8 *wlan_peer_get_macaddr(struct wlan_objmgr_peer *p) {assert(p);return p->mac;}
static struct wlan_objmgr_psoc *wlan_peer_get_psoc(struct wlan_objmgr_peer *p) {return wlan_vdev_get_psoc(p->vdev);}
static enum wlan_peer_type p89_peer_type(struct wlan_objmgr_peer *p) {return p->peer_mlme.peer_type;}
static QDF_STATUS p89_addr_equal(const u8 *a,const u8 *b) {return memcmp(a,b,6)?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;}
static int p89_atomic_read(qdf_atomic_t *p) {return p->value;}
static void p89_atomic_inc(qdf_atomic_t *p) {p->value++;}
static void p89_atomic_dec(qdf_atomic_t *p) {p->value--;}
static bool p89_atomic_dec_and_test(qdf_atomic_t *p) {p->value--;return !p->value;}
static void p89_check(struct wlan_objmgr_peer *p) {int sum=0;for(unsigned i=0;i<WLAN_REF_ID_MAX;i++){assert(p->peer_objmgr.ref_id_dbg[i].value>=0 && "EXPECTED_PEER_REFERENCE_ACCOUNTING");sum+=p->peer_objmgr.ref_id_dbg[i].value;}assert(sum==p->peer_objmgr.ref_cnt.value && "EXPECTED_PEER_REFERENCE_ACCOUNTING");}
static void p89_print_ids(qdf_atomic_t *ids,int level) {assert(ctx_peer && ids==ctx_peer->peer_objmgr.ref_id_dbg && level==QDF_TRACE_LEVEL_FATAL);}
static void wlan_objmgr_print_peer_ref_ids(struct wlan_objmgr_peer *p,int level) {assert(p==ctx_peer && level==QDF_TRACE_LEVEL_DEBUG);p89_check(p);}
static void p89_minidump_remove(void *p,size_t n,struct wlan_objmgr_psoc *parent,unsigned kind,const char *name) {assert(p==ctx_peer && n==sizeof(*ctx_peer) && parent==wma_context.psoc && kind==WLAN_MD_OBJMGR_PEER && !strcmp(name,"wlan_objmgr_peer"));}
static void p89_notify_delete(struct wlan_objmgr_peer *p,unsigned kind) {assert(p==ctx_peer && kind==WLAN_PEER_OP && p->obj_state==WLAN_OBJ_STATE_LOGICALLY_DELETED && !p->peer_lock && ctx_peer_present && !clean_peer_deleted);ctx_peer_present=false;clean_peer_deleted=true;}
static void p89_notify_destroy(struct wlan_objmgr_peer *p,unsigned kind) {assert(p==ctx_peer && kind==WLAN_PEER_OP && !p->peer_objmgr.ref_cnt.value && !p->peer_lock && clean_peer_unmapped && clean_peer_deleted && !clean_peer_users && !p89_destroy_calls && "EXPECTED_PEER_LAST_REFERENCE");p89_check(p);p89_destroy_calls++;}
static void p89_parent_get(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id) {assert(id==WLAN_OBJMGR_ID && v==ctx_peer->vdev);p89_parent_gets++;ref_selected_get(v,id);ref_check(v);}
static void p89_parent_put(struct wlan_objmgr_vdev *v,wlan_objmgr_ref_dbgid id) {assert(id==WLAN_OBJMGR_ID && v==last_vdev);p89_parent_puts++;ref_selected_release(v,id);ref_check(v);}
static void wlan_pdev_obj_lock(struct wlan_objmgr_pdev *p) {assert(!p->p89_lock);p->p89_lock=1;}
static void wlan_pdev_obj_unlock(struct wlan_objmgr_pdev *p) {assert(p->p89_lock);p->p89_lock=0;}
static void wlan_pdev_decr_peer_count(struct wlan_objmgr_pdev *p) {assert(p->p89_lock && p->p89_peer_count==1);p->p89_peer_count--;}
static void wlan_pdev_decr_temp_peer_count(struct wlan_objmgr_pdev *p) {(void)p;assert(!"UNSUPPORTED_TEMP_PEER");}
static struct wlan_objmgr_peer *wlan_vdev_get_selfpeer(struct wlan_objmgr_vdev *v) {return v->vdev_objmgr.self_peer;}
static void wlan_vdev_set_selfpeer(struct wlan_objmgr_vdev *v,struct wlan_objmgr_peer *p) {v->vdev_objmgr.self_peer=p;}
static struct wlan_objmgr_peer *wlan_vdev_get_bsspeer(struct wlan_objmgr_vdev *v) {return v->vdev_objmgr.bss_peer;}
static void wlan_vdev_set_bsspeer(struct wlan_objmgr_vdev *v,struct wlan_objmgr_peer *p) {v->vdev_objmgr.bss_peer=p;}
static QDF_STATUS wlan_obj_vdev_peerlist_remove_peer(int *list,struct wlan_objmgr_peer *p) {assert(p==ctx_peer && list==&p->vdev->vdev_objmgr.wlan_peer_list && *list==1 && p89_vdev_link);if(p89_mode==3)return QDF_STATUS_E_FAILURE;*list=0;p89_vdev_link=false;return QDF_STATUS_SUCCESS;}
static QDF_STATUS wlan_objmgr_psoc_peer_detach(struct wlan_objmgr_psoc *parent,struct wlan_objmgr_peer *p) {assert(parent==wma_context.psoc && p==ctx_peer && !p89_vdev_link && !p->vdev->vdev_objmgr.wlan_peer_count && p89_psoc_link);assert(p->vdev->vdev_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value==p89_parent_before && "EXPECTED_PEER_TEMP_VDEV_PIN");p89_psoc_detaches++;if(p89_mode==4)return QDF_STATUS_E_FAILURE;p89_psoc_link=false;return QDF_STATUS_SUCCESS;}
static void wlan_objmgr_peer_trace_del_ref_list(struct wlan_objmgr_peer *p) {assert(p==ctx_peer && !p89_vdev_link && !p89_psoc_link && !p->peer_objmgr.ref_cnt.value);}
static void wlan_objmgr_peer_trace_deinit_lock(struct wlan_objmgr_peer *p) {wlan_objmgr_peer_trace_del_ref_list(p);}
static void p89_spin_destroy(int *lock) {assert(ctx_peer && lock==&ctx_peer->peer_lock && !*lock && !p89_vdev_link && !p89_psoc_link);}
static void p89_storage_free(void *p) {assert(p==ctx_peer && p89_heap==1 && !p89_vdev_link && !p89_psoc_link && p89_order==2);free(p);ctx_peer=NULL;p89_heap--;p89_free_calls++;}
static void wlan_objmgr_vdev_peer_freed_notify(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);p89_notify_freed++;}
#pragma push_macro("QDF_ASSERT")
#pragma push_macro("QDF_BUG")
#pragma push_macro("obj_mgr_err")
#undef QDF_ASSERT
#undef QDF_BUG
#undef obj_mgr_err
#define QDF_ASSERT(x) p89_bug(x)
#define QDF_BUG(x) p89_bug(x)
#define WLAN_OBJMGR_BUG(x) p89_bug(x)
#define obj_mgr_err p89_log
#define obj_mgr_debug p89_log
#define WLAN_ADDR_EQ p89_addr_equal
#define wlan_peer_get_peer_type p89_peer_type
#define qdf_atomic_read p89_atomic_read
#define qdf_atomic_inc p89_atomic_inc
#define qdf_atomic_dec p89_atomic_dec
#define qdf_atomic_dec_and_test p89_atomic_dec_and_test
#define g_umac_glb_obj p89_handlers
#define wlan_objmgr_notify_destroy p89_notify_destroy
#define wlan_objmgr_notify_log_delete p89_notify_delete
#define wlan_minidump_remove p89_minidump_remove
#define wlan_objmgr_print_ref_ids p89_print_ids
#define qdf_spinlock_destroy p89_spin_destroy
#define qdf_mem_free p89_storage_free
#define wlan_objmgr_vdev_get_ref p89_parent_get
#define wlan_objmgr_vdev_release_ref p89_parent_put
#define wlan_objmgr_vdev_peer_detach p89_native_vdev_detach
NATIVE_VDEV_DETACH
#undef wlan_objmgr_vdev_peer_detach
#define wlan_objmgr_vdev_peer_detach p89_vdev_detach
#define wlan_objmgr_peer_obj_free p89_native_free
static void p89_native_release(struct wlan_objmgr_peer *,wlan_objmgr_ref_dbgid);
#define wlan_objmgr_peer_release_ref p89_native_release
NATIVE_PEER_FREE
#undef wlan_objmgr_peer_obj_free
#define wlan_objmgr_peer_obj_free p89_physical_free
#define wlan_objmgr_peer_object_status p89_native_status
#define wlan_objmgr_peer_component_obj_detach p89_native_component_detach
#define __wlan_objmgr_peer_obj_destroy p89_native_destroy_body
#define wlan_objmgr_peer_obj_destroy p89_native_destroy
#define wlan_objmgr_peer_get_debug_id_ref p89_native_get_id
#define wlan_objmgr_peer_release_debug_id_ref p89_native_put_id
#define wlan_objmgr_peer_get_ref p89_native_get
#define wlan_objmgr_peer_try_get_ref p89_native_try
#define wlan_objmgr_peer_obj_delete p89_native_delete
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
NATIVE_PEER_FUNCTIONS
#pragma GCC diagnostic pop
#undef wlan_objmgr_peer_obj_delete
#undef wlan_objmgr_peer_try_get_ref
#undef wlan_objmgr_peer_get_ref
#undef wlan_objmgr_peer_release_debug_id_ref
#undef wlan_objmgr_peer_get_debug_id_ref
#undef wlan_objmgr_peer_obj_destroy
#undef __wlan_objmgr_peer_obj_destroy
#undef wlan_objmgr_peer_component_obj_detach
#undef wlan_objmgr_peer_object_status
#undef wlan_objmgr_peer_release_ref
#undef wlan_objmgr_peer_obj_free
#undef wlan_objmgr_vdev_peer_detach
#undef wlan_objmgr_vdev_release_ref
#undef wlan_objmgr_vdev_get_ref
#undef qdf_mem_free
#undef qdf_spinlock_destroy
#undef wlan_objmgr_print_ref_ids
#undef wlan_minidump_remove
#undef wlan_objmgr_notify_log_delete
#undef wlan_objmgr_notify_destroy
#undef g_umac_glb_obj
#undef qdf_atomic_dec_and_test
#undef qdf_atomic_dec
#undef qdf_atomic_inc
#undef qdf_atomic_read
#undef wlan_peer_get_peer_type
#undef WLAN_ADDR_EQ
#undef obj_mgr_debug
#undef obj_mgr_err
#undef WLAN_OBJMGR_BUG
#undef QDF_BUG
#undef QDF_ASSERT
#pragma pop_macro("obj_mgr_err")
#pragma pop_macro("QDF_BUG")
#pragma pop_macro("QDF_ASSERT")
static QDF_STATUS p89_vdev_detach(struct wlan_objmgr_vdev *v,struct wlan_objmgr_peer *p) {p89_vdev_detaches++;QDF_STATUS ret=p89_native_vdev_detach(v,p);ctx_reset_peer_count=v->vdev_objmgr.wlan_peer_count;return ret;}
static QDF_STATUS p89_physical_free(struct wlan_objmgr_peer *p) {
 assert(!p89_async && "EXPECTED_PEER_COMPONENT_COMPLETION");
 struct wlan_objmgr_vdev *v=p->vdev;p89_parent_before=v->vdev_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value;
 QDF_STATUS ret=p89_native_free(p);p89_result=ret;
 if(!ret) {assert(!ctx_peer && !p89_heap && !p89_vdev_link && !p89_psoc_link && !ctx_reset_peer_count);assert(v->vdev_objmgr.ref_id_dbg[WLAN_OBJMGR_ID].value==p89_parent_before-1 && p89_parent_gets==1 && p89_parent_puts==2 && "EXPECTED_PEER_PARENT_PIN_BALANCE");assert(!p89_notify_freed);clean_peer_gone=true;if(clean_dp_deferred){clean_dp_deferred=false;finish_dp();}}
 return ret;
}
static QDF_STATUS p89_first_component(struct wlan_objmgr_peer *p,void *arg) {assert(p==ctx_peer && arg==&p89_registry && !p89_order && "EXPECTED_PEER_COMPONENT_FORWARD_ORDER");p89_order=1;void *token=p->peer_comp_priv_obj[0];assert(token && !p89_native_component_detach(p,0,token));free(token);return QDF_STATUS_SUCCESS;}
static QDF_STATUS p89_last_component(struct wlan_objmgr_peer *p,void *arg) {assert(p==ctx_peer && arg==&p89_registry && p89_order==1 && "EXPECTED_PEER_COMPONENT_FORWARD_ORDER");p89_order=2;unsigned id=WLAN_UMAC_COMP_ID_MAX-1;void *token=p->peer_comp_priv_obj[id];assert(token);if(p89_mode==2)return QDF_STATUS_E_FAILURE;if(p89_mode==1 || p89_mode==5){p89_async=token;p->peer_comp_priv_obj[id]=NULL;return QDF_STATUS_COMP_ASYNC;}assert(!p89_native_component_detach(p,id,token));free(token);return QDF_STATUS_SUCCESS;}
static void p89_create(struct wlan_objmgr_vdev *v) {
 assert(!ctx_peer && !p89_heap && !v->vdev_objmgr.wlan_peer_count && !v->pdev->p89_peer_count);ctx_peer=calloc(1,sizeof(*ctx_peer));assert(ctx_peer);p89_heap=1;ctx_peer->vdev=v;ctx_peer->obj_state=WLAN_OBJ_STATE_CREATED;ctx_peer->peer_mlme.peer_type=WLAN_PEER_SELF;memcpy(ctx_peer->mac,v->mac,6);
 for(unsigned i=0;i<WLAN_UMAC_MAX_COMPONENTS;i++)ctx_peer->obj_status[i]=QDF_STATUS_COMP_DISABLED;
 memset(&p89_registry,0,sizeof(p89_registry));unsigned ids[]={0,WLAN_UMAC_COMP_ID_MAX-1};for(unsigned i=0;i<2;i++){unsigned id=ids[i];ctx_peer->peer_comp_priv_obj[id]=malloc(1);assert(ctx_peer->peer_comp_priv_obj[id]);ctx_peer->obj_status[id]=QDF_STATUS_SUCCESS;p89_registry.peer_destroy_handler_arg[id]=&p89_registry;}
 p89_registry.peer_destroy_handler[0]=p89_first_component;p89_registry.peer_destroy_handler[WLAN_UMAC_COMP_ID_MAX-1]=p89_last_component;
 p89_native_get(ctx_peer,WLAN_OBJMGR_ID);p89_native_get(ctx_peer,WLAN_DP_ID);if(p89_mode==6)p89_native_get(ctx_peer,REF_NATIVE_OSIF);p89_check(ctx_peer);
 v->vdev_objmgr.wlan_peer_count=v->vdev_objmgr.wlan_peer_list=1;v->vdev_objmgr.self_peer=ctx_peer;v->vdev_objmgr.bss_peer=p89_bss?ctx_peer:NULL;v->pdev->p89_peer_count=1;p89_vdev_link=p89_psoc_link=true;
 ref_selected_get(v,WLAN_OBJMGR_ID);ref_check(v);
}
'''
LATE=r'''
static bool p89_complete(struct mishare_runtime_owner **o) {
 if(!clean_peer_unmapped) {assert(ctx_peer && clean_peer_deleted && p89_heap==1 && ctx_reset_peer_count==1 && pending_dp_cb);assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls && "EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE");clean_peer_unmap();}
 if(p89_mode==1 || p89_mode==5) {
  assert(ctx_peer && p89_heap==1 && p89_async && p89_destroy_calls==1 && ctx_peer->obj_state==WLAN_OBJ_STATE_PARTIALLY_DELETED && !ctx_peer->peer_objmgr.ref_cnt.value && !p89_free_calls && !clean_peer_gone);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls && !detach_calls);
  unsigned id=WLAN_UMAC_COMP_ID_MAX-1;if(p89_mode==5){assert(p89_native_component_detach(ctx_peer,id,&p89_bad)==QDF_STATUS_E_FAILURE);assert(ctx_peer->obj_status[id]==QDF_STATUS_E_FAILURE && !p89_free_calls && p89_async);return false;}
  free(p89_async);p89_async=NULL;assert(!p89_native_component_detach(ctx_peer,id,NULL));
 }
 if(p89_mode==6) {assert(ctx_peer && clean_peer_unmapped && clean_peer_deleted && ctx_peer->peer_objmgr.ref_cnt.value==1 && !p89_destroy_calls && !clean_peer_gone);assert(p89_native_try(ctx_peer,REF_NATIVE_OSIF)==QDF_STATUS_E_RESOURCES && "EXPECTED_PEER_REFERENCE_ADMISSION");assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls);p89_native_release(ctx_peer,REF_NATIVE_OSIF);}
 if(p89_mode>=2 && p89_mode<=4) {
  assert(ctx_peer && p89_heap==1 && !clean_peer_gone && p89_destroy_calls==1 && !p89_free_calls && !delete_calls && !detach_calls && engine_allocations==1 && dp_objects && pending_dp_cb);
  if(p89_mode==2)assert(p89_bugs==1 && !p89_vdev_detaches && p89_vdev_link && p89_psoc_link && ctx_reset_peer_count==1);
  if(p89_mode==3)assert(!p89_bugs && p89_result==QDF_STATUS_E_FAILURE && p89_vdev_detaches==1 && p89_vdev_link && p89_psoc_link && ctx_reset_peer_count==1 && p89_parent_puts==1 && !ctx_peer->vdev->vdev_objmgr.self_peer);
  if(p89_mode==4)assert(!p89_bugs && p89_result==QDF_STATUS_E_FAILURE && !p89_vdev_link && p89_psoc_link && !ctx_reset_peer_count && p89_parent_puts==2);
  assert(mishare_runtime_destroy(o)==-EINPROGRESS && !delete_calls && !detach_calls);return false;
 }
 assert(clean_peer_gone && !ctx_peer && !p89_heap && p89_free_calls==1 && p89_vdev_detaches==1 && p89_psoc_detaches==1 && !p89_bugs);
 if(pending_dp_cb) {finish_dp();}
 return true;
}
'''
EXTRA=r'''
static void p89_extra_cases(void) {
 for(unsigned mode=1;mode<=6;mode++)for(unsigned inline_unmap=0;inline_unmap<2;inline_unmap++){pid_t c=fork();assert(c>=0);if(!c){p89_mode=mode;p89_bss=inline_unmap;clean_modes=inline_unmap?2:0;engine_cycle(5240,false,0);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));}
}
'''

def direct_destroy(text):
 variants=re.findall(r'(?:static\s+)?QDF_STATUS\s+wlan_objmgr_peer_obj_destroy\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)
 assert len(variants)==2 and 'return __wlan_objmgr_peer_obj_destroy(peer);' in variants[-1]
 return variants[-1]

def fixture(root):
 source,exits,stubbed=previous.fixture(root);peer=(root/PEER).read_text();vdev=(root/VDEV).read_text();common=(root/COMMON).read_text()
 enum=re.search(r'^enum wlan_peer_type \{.*?^\};',common,re.M|re.S)[0]
 named='struct wlan_objmgr_peer;\n'+enum+'\nstruct wlan_objmgr_vdev_objmgr {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt;uint8_t vdev_id;unsigned wlan_peer_count;int wlan_peer_list;struct wlan_objmgr_peer *self_peer,*bss_peer;};\n'
 source=owner.replace_once(source,'struct wlan_objmgr_vdev {',named+'struct wlan_objmgr_vdev {')
 source=owner.replace_once(source,'struct {qdf_atomic_t ref_cnt,ref_id_dbg[WLAN_REF_ID_MAX];unsigned print_cnt;uint8_t vdev_id;} vdev_objmgr;','struct wlan_objmgr_vdev_objmgr vdev_objmgr;')
 source=owner.replace_once(source,'struct wlan_objmgr_pdev { struct wlan_objmgr_psoc *psoc; };','struct wlan_objmgr_pdev { struct wlan_objmgr_psoc *psoc;int p89_lock,p89_peer_count; };')
 source=owner.replace_once(source,'pdev={&psoc}','pdev={.psoc=&psoc}')
 source=owner.replace_once(source,'struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;};',STRUCT)
 source=owner.replace_once(source,'static struct wlan_objmgr_peer ctx_peer;','static struct wlan_objmgr_peer *ctx_peer;')
 source=source.replace('&ctx_peer','ctx_peer').replace('ctx_peer.vdev','ctx_peer->vdev')
 native='\n'.join(function(peer,n) for n in ['wlan_objmgr_peer_object_status','wlan_objmgr_peer_component_obj_detach','__wlan_objmgr_peer_obj_destroy'])+'\n'+direct_destroy(peer)+'\n'+'\n'.join(function(peer,n) for n in ['wlan_objmgr_peer_get_debug_id_ref','wlan_objmgr_peer_release_debug_id_ref','wlan_objmgr_peer_get_ref','wlan_objmgr_peer_try_get_ref','wlan_objmgr_peer_release_ref','wlan_objmgr_peer_obj_delete'])
 block=SUPPORT.replace('\nNATIVE_VDEV_DETACH\n','\n'+function(vdev,'wlan_objmgr_vdev_peer_detach')+'\n').replace('\nNATIVE_PEER_FREE\n','\n'+function(peer,'wlan_objmgr_peer_obj_free')+'\n').replace('\nNATIVE_PEER_FUNCTIONS\n','\n'+native+'\n')
 anchor='static struct wlan_objmgr_vdev *wlan_peer_get_vdev(struct wlan_objmgr_peer *p) {return p->vdev;}'
 source=owner.replace_once(source,anchor,anchor+'\n'+block)
 source=owner.replace_once(source,'ctx_peer_present=true;ctx_peer->vdev=w->interfaces[id].vdev;','ctx_peer_present=true;p89_create(w->interfaces[id].vdev);')
 old=function(source,'clean_peer_unmap');new='static void clean_peer_unmap(void) {\n assert(clean_active && clean_peer_dp_deletes==1 && !clean_peer_unmapped && ctx_peer);clean_peer_unmapped=true;p89_native_release(ctx_peer,WLAN_DP_ID);if(ctx_peer)p89_check(ctx_peer);\n}'
 source=owner.replace_once(source,old,new)
 for name,new in [
 ('clean_get_peer_mac','static struct wlan_objmgr_peer *clean_get_peer_mac(struct wlan_objmgr_psoc *p,u8 *mac,int ref) {assert(clean_active && p==wma_context.psoc && mac && ref==WLAN_LEGACY_WMA_ID && ctx_peer_present && !clean_peer_deleted);assert(!p89_native_try(ctx_peer,REF_NATIVE_WMA));clean_peer_users++;p89_check(ctx_peer);return ctx_peer;}'),
 ('clean_release_peer','static void clean_release_peer(struct wlan_objmgr_peer *p,int ref) {assert(p==ctx_peer && ref==WLAN_LEGACY_WMA_ID && clean_peer_users);clean_peer_users--;p89_native_release(p,REF_NATIVE_WMA);if(ctx_peer)p89_check(ctx_peer);}'),
 ('clean_obj_delete','static QDF_STATUS clean_obj_delete(struct wlan_objmgr_peer *p) {assert(p==ctx_peer && clean_peer_phase==4 && clean_peer_users==1 && !clean_peer_deleted && ctx_peer_present);clean_peer_phase=5;clean_obj_deletes++;QDF_STATUS ret=p89_native_delete(p);p89_check(p);return ret;}')]:
  old=re.search(r'^static [^\n]*\b'+name+r'\([^\n]*$',source,re.M)[0];source=owner.replace_once(source,old,new)
 old=function(source,'clean_try_peer_gone');source=owner.replace_once(source,old,'static void clean_try_peer_gone(void) {\n assert(!clean_peer_gone || (!ctx_peer && !p89_heap));\n}')
 source=owner.replace_once(source,'static void clean_end(',LATE+'\nstatic void clean_end(')
 clean=function(source,'clean_end');a=clean.index(' if(!clean_peer_gone) {');b=clean.index(' assert(clean_peer_gone && !ctx_reset_peer_count',a)
 changed=clean[:a]+' if(!p89_complete(o))return;\n'+clean[b:];source=owner.replace_once(source,clean,changed)
 arm=function(source,'ref_arm_components');source=owner.replace_once(source,arm,arm.replace('{','{\n assert(!ctx_peer && clean_peer_gone && "EXPECTED_DP_COMPLETION_BEFORE_SM_DELETE");',1))
 main=function(source,'ref_baseline');changed=owner.replace_once(main,'ref_extra_cases();','ref_extra_cases();p89_extra_cases();');source=owner.replace_once(source,main,EXTRA+'\n'+changed)
 for name in NAMES:assert source.count(function(peer,name))==1,name
 assert source.count(direct_destroy(peer))==1
 assert source.count(function(vdev,'wlan_objmgr_vdev_peer_detach'))==1
 return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 previous.negative_controls(directory,c_file,command,env,source,root);exe=directory/'engine'
 controls=[('peer_last_reference','wlan_objmgr_peer_release_ref','if (qdf_atomic_dec_and_test(&peer->peer_objmgr.ref_cnt)) {','if ((qdf_atomic_dec_and_test(&peer->peer_objmgr.ref_cnt),true)) {','EXPECTED_PEER_LAST_REFERENCE',0),('peer_component_order','__wlan_objmgr_peer_obj_destroy','for (id = 0; id < WLAN_UMAC_MAX_COMPONENTS; id++)','for (id = WLAN_UMAC_MAX_COMPONENTS-1; id < WLAN_UMAC_MAX_COMPONENTS; id--)','EXPECTED_PEER_COMPONENT_FORWARD_ORDER',0),('peer_async_wait','__wlan_objmgr_peer_obj_destroy','if (obj_status == QDF_STATUS_COMP_ASYNC) {','if (false) {','EXPECTED_PEER_COMPONENT_COMPLETION',1),('peer_parent_pin','wlan_objmgr_peer_obj_free','wlan_objmgr_vdev_get_ref(vdev, WLAN_OBJMGR_ID);','/* negative: omit temporary VDEV pin */','EXPECTED_PEER_TEMP_VDEV_PIN',0),('peer_parent_put','wlan_objmgr_peer_obj_free','wlan_objmgr_vdev_release_ref(vdev, WLAN_OBJMGR_ID);\n\n\treturn QDF_STATUS_SUCCESS;','/* negative: omit final temporary pin release */\n\n\treturn QDF_STATUS_SUCCESS;','EXPECTED_PEER_PARENT_PIN_BALANCE',0)]
 for label,name,needle,mutation,marker,mode in controls:
  target=owner.replace_once(source,function(source,'main'),f'int main(void) {{p89_mode={mode};engine_cycle(5240,false,0);_Exit(0);}}');c_file.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
  body=function(target,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-300:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_PEER_DESTRUCTOR_FIXTURE_PASS_ONLY'
 r['native_peer_function_sha256']={n:hashlib.sha256(function((root/PEER).read_text(),n).encode()).hexdigest() for n in NAMES};r['native_peer_direct_destroy_sha256']=hashlib.sha256(direct_destroy((root/PEER).read_text()).encode()).hexdigest();r['native_vdev_peer_detach_sha256']=hashlib.sha256(function((root/VDEV).read_text(),'wlan_objmgr_vdev_peer_detach').encode()).hexdigest()
 prior=previous.PARENT_CONTROLS+[label+suffix for suffix in ['','_debug'] for label in ['last_reference','reference_id_gate','reference_accounting','reference_admission']]+['logical_delete_reference_release']
 for name in prior+['peer_last_reference','peer_component_order','peer_async_wait','peer_parent_pin','peer_parent_put']:r['negative_control_'+name+'_rejected']=True
 r['checks']=['native self-peer get/try/release, debug-ID helpers, logical delete, forward component dispatch, status/component detach, storage free and native VDEV peer detach','original peer type enum; modeled heap creation establishes real 0088 native VDEV OBJMGR pin and peer OBJMGR/DP references','DP unmap endpoint releases an actual native peer DP reference; WMA references and delayed unmap jointly determine the native zero-ref branch','native peer free temporarily pins VDEV, native VDEV detach removes self/BSS links and decrements VDEV/PDEV peer counts and drops the peer VDEV pin, then PSOC detach, peer storage free, final temporary VDEV put','0088 complete suite and additional three-VDEV-ref sequences run under both VDEV trace modes','24 additional component/reference cases: peer component async, component failure, VDEV list failure, PSOC detach failure, bad async token, extra peer reference; each with inline/deferred unmap under both VDEV trace modes','native detach failures retain partial effects: VDEV list failure may already clear self/BSS; PSOC failure follows successful VDEV detach and peer-pin release','all previous twenty-four negatives and five peer zero/order/ASYNC/temporary-pin/final-put mutations rejected']
 r['limitations']='Native peer destruction and VDEV peer-detach bodies execute for a single private self peer. Peer reference APIs use the non-trace variant with original debug-ID checking helpers; peer trace database and FEATURE_DELAYED_PEER_OBJ_DESTROY workqueue variant are not exercised. Heap creation, component registration/two sentinel handlers, QDF locks/atomic operations, DP unmap producer, PSOC/list operations and PDEV accounting endpoints remain platform models. The actual native VDEV peer-detach body, peer storage free and 0088 VDEV reference functions run; VDEV attachment setup is modeled, not native attach/create. DP VDEV completion is explicitly gated by the model until actual modeled peer storage free plus final temporary VDEV put; this does not certify the real DP-to-object-manager callback graph, concurrency, automatic parent lease or native shutdown coordinator. Both 0088 VDEV trace modes remain covered, but no peer trace-mode/configuration parity claim. Temporary peers, STA/BSS ref recursion and non-self peer notification paths abort or remain unselected. Controlled native BUG branches are modeled traps; partial failures preserve the unfinished remainder until child process exit, without rolling back earlier detach/component frees. Active START/UP SSR recovery, backend activation, phone/firmware/RF and AirDrop certification remain absent.'
 return r

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
