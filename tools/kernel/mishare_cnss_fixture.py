#!/usr/bin/env python3
"""Actions-only native PCIe consumer + CNSS2 checked unregister, modeled HW."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_execution_fixture import COMMON, extract

ROOT=Path(__file__).resolve().parents[2]
FILES=['platform/cnss2/main.h','platform/cnss2/pci.h','platform/cnss2/bus.h','platform/cnss2/bus.c','platform/cnss2/main.c','platform/inc/cnss2.h','platform/cnss2/pci.c','platform/cnss2/debug.c','platform/cnss2/power.c','platform/cnss_utils/cnss_common.h','platform/cnss_utils/wlan_firmware_service_v01.h']
BODY=r'''
#define CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER 1
#define BIT(x) (1UL<<(x))
static bool test_bit(int n,const unsigned long *s){return !!(*s&BIT(n));}
static void set_bit(int n,unsigned long *s){*s|=BIT(n);}
static void clear_bit(int n,unsigned long *s){*s&=~BIT(n);}
#define cnss_pr_err(...) ((void)0)
#define cnss_pr_dbg(...) ((void)0)
#define CNSS_ASSERT(x) assert(x)
#define CNSS_BUS_PCI 3
#define CNSS_BUS_WIDTH_NONE 0
#define CNSS_EVENT_SYNC_UNKILLABLE 5
#define CNSS_TIMEOUT_WLAN_WATCHDOG 7
#define CNSS_TIMEOUT_RECOVERY 8
#define msecs_to_jiffies(x) (x)
#define PLD_BUS_TYPE_PCIE 77
NATIVE_DEVICE_ID
NATIVE_ENUM
struct pci_dev {struct device dev;};
struct pci_device_id {int id;};
struct platform_device {struct device dev;};
#include "execution.c"
struct cnss_wlan_driver {
 void (*remove)(struct pci_dev *);
 int (*reinit)(struct pci_dev *,const struct pci_device_id *);
 void (*shutdown)(struct pci_dev *);
 int (*idle_restart)(struct pci_dev *,const struct pci_device_id *);
 int (*idle_shutdown)(struct pci_dev *);
};
struct cnss_plat_data {
 unsigned long driver_state;int device_id,bus_type;
 struct mutex driver_ops_lock;void *bus_priv;struct platform_device *plat_dev;
 struct {bool dumping_bt_over_wl;} xdump_helper;
 struct {bool dump_data_valid;} ramdump_info_v2;
 bool pm_suspend_in_progress,recovery_enabled;
 int power_up_complete,recovery_complete,rddm_complete;
 void *get_info_cb_ctx,*get_info_cb,*get_driver_async_data_ctx,*get_driver_async_data_cb;
};
struct cnss_pci_data {
 struct cnss_plat_data *plat_priv;struct pci_dev *pci_dev;
 struct cnss_wlan_driver *driver_ops;int device_id,remap_window;bool pci_link_down_ind;
};
NATIVE_GUARD
static struct pci_dev pdev={{9}};
static struct platform_device plat_dev={{10}};
static struct cnss_plat_data plat={.driver_ops_lock={PTHREAD_MUTEX_INITIALIZER}};
static struct cnss_pci_data pci;
static int post_error,link_error,remove_error,trans_error,register_error;
static int native_removed,sync_unregistered,sync_destroyed,del_dev_count,other_bus_calls;
static int power_off,mhi_off,mhi_deinit,bandwidth_off,time_sync_stop,pm_resume,posts;
static bool context_missing,link_resume_fail,plat_missing;
static int print_optimize;
struct pld_ops {
 void (*remove)(struct device *,int);
 int (*reinit)(struct device *,int,void *,void *);
 void (*shutdown)(struct device *,int);
 int (*idle_restart)(struct device *,int);
 int (*idle_shutdown)(struct device *,int);
};
struct pld_context {struct pld_ops *ops;int pld_driver_state;};
static struct pld_ops hdd_ops;
static struct pld_context context;
static struct pld_context *pld_get_global_context(void){return context_missing?NULL:&context;}
struct osif_psoc_sync {int active;};static struct osif_psoc_sync sync;
static bool cds_is_pcie_link_resume_fail(void){return link_resume_fail;}
static void cds_set_driver_loaded(bool b){(void)b;}
static void cds_set_unload_in_progress(bool b){(void)b;}
static int osif_psoc_sync_trans_start_wait(struct device *d,struct osif_psoc_sync **s){assert(d==&pdev.dev);*s=&sync;return trans_error;}
static void osif_psoc_sync_wait_for_ops(struct osif_psoc_sync *s){assert(s==&sync);}
static void osif_psoc_sync_unregister(struct device *d){assert(d==&pdev.dev);sync_unregistered++;}
static void osif_psoc_sync_trans_stop(struct osif_psoc_sync *s){assert(s==&sync);}
static void osif_psoc_sync_destroy(struct osif_psoc_sync *s){assert(s==&sync);sync_destroyed++;}
static int hdd_mishare_remove_prepare(struct device *d){assert(d==&pdev.dev);return remove_error;}
static void pld_del_dev(struct pld_context *c,struct device *d){assert(c==&context && d==&pdev.dev);del_dev_count++;}
static void hdd_remove(struct device *d,int bus){assert(d==&pdev.dev && bus==77);native_removed++;}
static int hdd_reinit(struct device *d,int bus,void *bdev,void *id){(void)d;(void)bus;(void)bdev;(void)id;return 0;}
static void hdd_shutdown(struct device *d,int bus){(void)d;(void)bus;}
static int hdd_idle(struct device *d,int bus){(void)d;(void)bus;return 0;}
NATIVE_PL_CALLBACKS
NATIVE_PL_REMOVE
static struct cnss_wlan_driver pld_pcie_ops={
NATIVE_PL_SLOTS
};
static int cnss_wlan_register_driver(struct cnss_wlan_driver *ops){
 assert(ops==&pld_pcie_ops && ops->reinit==opairshare_wlan_execution_pcie_reinit && ops->shutdown==opairshare_wlan_execution_pcie_shutdown && ops->idle_restart==opairshare_wlan_execution_pcie_idle_restart && ops->idle_shutdown==opairshare_wlan_execution_pcie_idle_shutdown && "EXPECTED_PCIE_CNSS_SLOTS");
 if(!register_error)pci.driver_ops=ops;return register_error;
}
static int cnss_wlan_unregister_driver_checked_v1(struct cnss_wlan_driver *,int (*)(struct device *));
NATIVE_PL_DESCRIPTOR
NATIVE_PL_REGISTER
NATIVE_PL_CHECKED
NATIVE_PL_UNREGISTER
static int pld_ipci_unregister_driver_checked(void){return 0;}
static void pld_snoc_fw_sim_unregister_driver(void){other_bus_calls++;}
static void pld_pcie_fw_sim_unregister_driver(void){other_bus_calls++;}
static void pld_snoc_unregister_driver(void){other_bus_calls++;}
static void pld_sdio_unregister_driver(void){other_bus_calls++;}
static void pld_usb_unregister_driver(void){other_bus_calls++;}
NATIVE_COMMON_CHECKED
NATIVE_HDD_CHECKED
#define hdd_err(...) ((void)0)
static int component_deinits;
static void late_unload(void){int mishare_ret;NATIVE_LATE_GUARD component_deinits++;}
static struct cnss_plat_data *cnss_get_plat_priv_by_driver_ops(struct cnss_wlan_driver *ops){(void)ops;return plat_missing?NULL:&plat;}
static unsigned int cnss_get_timeout(struct cnss_plat_data *p,int what){(void)p;(void)what;return 1;}
static int wait_for_completion_timeout(int *c,unsigned int timeout){(void)c;(void)timeout;return 1;}
static void reinit_completion(int *c){(void)c;}
static bool cnss_pci_is_rddm_state(struct cnss_plat_data *p){(void)p;return false;}
static void complete(int *c){(void)c;}
static void cnss_pci_stop_time_sync_update(struct cnss_pci_data *p){assert(p==&pci);time_sync_stop++;}
static void cnss_pci_pm_runtime_resume(struct cnss_pci_data *p){assert(p==&pci);pm_resume++;}
static void cnss_request_bus_bandwidth(struct device *d,int v){(void)d;(void)v;bandwidth_off++;}
static void cnss_pci_set_monitor_wake_intr(struct cnss_pci_data *p,bool b){(void)p;(void)b;}
static void cnss_pci_set_auto_suspended(struct cnss_pci_data *p,int v){(void)p;(void)v;}
static void cnss_del_rddm_timer(struct cnss_pci_data *p){(void)p;}
static int cnss_pci_collect_dump_info(struct cnss_pci_data *p,bool b){(void)p;(void)b;return 0;}
static bool cnss_is_device_powered_on(struct cnss_plat_data *p){(void)p;return true;}
static void cnss_pci_set_wlaon_pwr_ctrl(struct cnss_pci_data *p,bool a,bool b,int c){(void)p;(void)a;(void)b;(void)c;}
static void cnss_pci_power_off_mhi(struct cnss_pci_data *p,bool b){(void)p;(void)b;mhi_off++;}
static int cnss_disable_pcie_device(struct cnss_pci_data *p){(void)p;return 0;}
static int cnss_suspend_pci_link(struct cnss_pci_data *p){(void)p;return link_error;}
static void cnss_pci_deinit_mhi(struct cnss_pci_data *p){(void)p;mhi_deinit++;}
static void cnss_power_off_device(struct cnss_plat_data *p){(void)p;power_off++;}
NATIVE_REMOVE_INTERNAL
NATIVE_REMOVE_WRAPPER
NATIVE_SHUTDOWN_INTERNAL
NATIVE_SHUTDOWN_WRAPPER
static int cnss_pci_dev_shutdown(struct cnss_pci_data *p){return cnss_qca6290_shutdown(p);}
NATIVE_LEGACY_HANDLER
NATIVE_CHECKED_HANDLER
NATIVE_BUS_CHECKED
struct event_model {struct cnss_plat_data *p;int type;void *data;int ret;};
static void *event_thread(void *value){
 struct event_model *event=value;struct cnss_plat_data *plat_priv=event->p;int ret=-EINVAL;
 switch(event->type){NATIVE_EVENT_ROUTE default:assert(false);}
 event->ret=ret;return NULL;
}
static int cnss_bus_unregister_driver_hdlr(struct cnss_plat_data *p){return cnss_pci_unregister_driver_hdlr(p->bus_priv);}
static int cnss_driver_event_post(struct cnss_plat_data *p,int type,int flags,void *data){
 assert(flags==CNSS_EVENT_SYNC_UNKILLABLE && "EXPECTED_CNSS_SYNC_EVENT");posts++;
 if(post_error)return post_error;
 struct event_model e={p,type,data,-EINPROGRESS};pthread_t thread;
 assert(!pthread_create(&thread,NULL,event_thread,&e));assert(!pthread_join(thread,NULL));return e.ret;
}
NATIVE_CHECKED_ENTRY
NATIVE_LEGACY_ENTRY
static void no_receipt(struct pci_dev *p){(void)p;}
static void reset(void){
 assert(!execution_ops.owner && !execution_pcie_ops.owner && !execution_active && !atomic_load(&wlan_module.refs));
 atomic_store(&wlan_module.deny,false);post_error=link_error=remove_error=trans_error=register_error=0;
 native_removed=sync_unregistered=sync_destroyed=del_dev_count=other_bus_calls=0;
 power_off=mhi_off=mhi_deinit=bandwidth_off=time_sync_stop=pm_resume=posts=component_deinits=0;
 context_missing=link_resume_fail=plat_missing=false;
 hdd_ops=(struct pld_ops){hdd_remove,hdd_reinit,hdd_shutdown,hdd_idle,hdd_idle};context=(struct pld_context){&hdd_ops,1};
 plat.driver_state=BIT(CNSS_DRIVER_PROBED)|BIT(CNSS_DRIVER_REGISTERED)|BIT(CNSS_FW_READY)|BIT(CNSS_FW_MEM_READY);
 plat.device_id=PEACH_DEVICE_ID;plat.bus_type=CNSS_BUS_PCI;plat.bus_priv=&pci;plat.plat_dev=&plat_dev;
 plat.pm_suspend_in_progress=plat.ramdump_info_v2.dump_data_valid=plat.xdump_helper.dumping_bt_over_wl=false;
 pci=(struct cnss_pci_data){.plat_priv=&plat,.pci_dev=&pdev,.device_id=PEACH_DEVICE_ID};
}
static void retained_failure(int kind){
 reset();assert(!pld_pcie_register_driver());int expected=-EBUSY;
 switch(kind){
 case 0:remove_error=expected=-EINPROGRESS;break;
 case 1:remove_error=expected=-EUCLEAN;break;
 case 2:trans_error=-EBUSY;break;
 case 3:context_missing=true;expected=-ENODEV;break;
 case 4:context.ops=NULL;expected=-ENODEV;break;
 case 5:link_resume_fail=true;break;
 case 6:post_error=expected=-ENOMEM;break;
 case 7:pld_pcie_ops.remove=no_receipt;expected=-ENODATA;break;
 case 8:link_error=expected=-EIO;break;
 }
 if(kind!=3 && kind!=4){late_unload();assert(!component_deinits && "EXPECTED_CNSS_LATE_RETAINED");}
 else assert(pld_pcie_unregister_driver_checked()==-ENODEV);
 assert(unregister_scope && execution_pcie_ops.owner==THIS_MODULE && atomic_load(&wlan_module.refs)==1 && "EXPECTED_CNSS_PIN_RETAINED");
 assert(test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL,&plat.driver_state) && pci.driver_ops && test_bit(CNSS_DRIVER_REGISTERED,&plat.driver_state) && "EXPECTED_CNSS_PLATFORM_RETAINED");
 assert(!other_bus_calls && !power_off && !mhi_deinit && "EXPECTED_CNSS_NO_POWER_TAIL");
 if(kind!=8)assert(!native_removed && !sync_unregistered && !sync_destroyed && !del_dev_count && test_bit(CNSS_DRIVER_PROBED,&plat.driver_state) && "EXPECTED_CNSS_NO_WLAN_TEARDOWN");
 else assert(native_removed==1 && !test_bit(CNSS_DRIVER_PROBED,&plat.driver_state) && mhi_off==1 && "EXPECTED_CNSS_PARTIAL_TAIL_RETAINED");
 int before=posts;
 assert(pld_pcie_unregister_driver_checked()==expected && posts==before && "EXPECTED_CNSS_NO_REPLAY");
 assert(cnss_wlan_unregister_driver_checked_v1(&pld_pcie_ops,opairshare_wlan_execution_remove_status)==-ESHUTDOWN && posts==before);
 cnss_wlan_unregister_driver(&pld_pcie_ops);assert(posts==before && "EXPECTED_CNSS_NO_LEGACY_BYPASS");
 assert(cnss_pci_unregister_driver_hdlr(&pci)==-ESHUTDOWN);
 assert(cnss_pci_call_driver_remove(&pci)==-ESHUTDOWN);
 assert(cnss_qca6290_shutdown(&pci)==-ESHUTDOWN && !power_off);
}
static void admission_failure(int kind){
 reset();assert(!pld_pcie_register_driver());
 switch(kind){
 case 0:clear_bit(CNSS_DRIVER_PROBED,&plat.driver_state);break;
 case 1:set_bit(CNSS_DRIVER_RECOVERY,&plat.driver_state);break;
 case 2:plat.pm_suspend_in_progress=true;break;
 case 3:plat.ramdump_info_v2.dump_data_valid=true;break;
 case 4:pci.pci_link_down_ind=true;break;
 case 5:set_bit(CNSS_DRIVER_IDLE_SHUTDOWN,&plat.driver_state);break;
 case 6:plat.xdump_helper.dumping_bt_over_wl=true;break;
 }
 int ret=pld_pcie_unregister_driver_checked();assert(ret<0 && unregister_scope && atomic_load(&wlan_module.refs)==1);
 assert(!native_removed && !power_off && !mhi_off && !pm_resume && pci.driver_ops && "EXPECTED_CNSS_ADMISSION");
 assert(test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL,&plat.driver_state));
}
static void isolated(void (*f)(int),int n){for(int k=0;k<n;k++){pid_t p=fork();assert(p>=0);if(!p){f(k);_Exit(0);}int status;assert(waitpid(p,&status,0)==p && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_CNSS_CHILD");}}
int main(void){
 isolated(retained_failure,9);isolated(admission_failure,7);
 for(int borrowed=0;borrowed<2;borrowed++){
  reset();assert(!pld_pcie_register_driver());atomic_store(&wlan_module.deny,borrowed);
  int gets=atomic_load(&execution_get_count);assert(!wlan_hdd_unregister_driver_checked());
  assert(!context.ops && !context.pld_driver_state && other_bus_calls==5 && "EXPECTED_CNSS_SUCCESS_CHAIN");
  assert(!execution_ops.owner && !execution_pcie_ops.owner && !unregister_scope && !atomic_load(&wlan_module.refs));
  assert(native_removed==1 && sync_destroyed==1 && del_dev_count==1 && power_off==1 && mhi_deinit==1 && !pci.driver_ops && "EXPECTED_CNSS_SUCCESS_POWER");
  assert(!test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL,&plat.driver_state));
  assert(atomic_load(&execution_get_count)==gets+!borrowed);
 }
 reset();register_error=-EIO;assert(pld_pcie_register_driver()==-EIO && !execution_ops.owner && !execution_pcie_ops.owner);
 reset();assert(!pld_pcie_register_driver());
 struct cnss_wlan_driver foreign=pld_pcie_ops;
 assert(cnss_wlan_unregister_driver_checked_v1(&foreign,opairshare_wlan_execution_remove_status)==-ENOENT && !test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL,&plat.driver_state));
 assert(!pld_pcie_unregister_driver_checked());
 assert(!atomic_load(&foreign_module.refs));
 puts("MISHARE_CNSS_CHECKED_FIXTURE_PASS_ONLY");return 0;
}
'''


def native_function(text,name):return extract(text,r'^(?:static )?(?:int|void) '+name+r'\([^;{]+?\)\s*\{.*?^\}')


def verify_platform_origin(wlan):
    # All eleven platform files are restored byte-for-byte by just this patch.
    with tempfile.TemporaryDirectory() as tmp:
        t=Path(tmp)
        for f in FILES:(t/f).parent.mkdir(parents=True,exist_ok=True);(t/f).write_bytes((wlan/f).read_bytes())
        subprocess.run(['git','apply','--reverse',str(ROOT/'kernel/patches/popsicle/0061-restore-upstream-TSF-SMMU-Wonder-and-direct-refill.patch')],cwd=t,check=True,capture_output=True)
        subprocess.run(['git','apply','--reverse',str(ROOT/'kernel/patches/popsicle/0060-CNSS2-terminal-state-debug-and-local-helper.patch')],cwd=t,check=True,capture_output=True)
        subprocess.run(['git','apply','--reverse',str(ROOT/'kernel/patches/popsicle/0059-select-real-SoC-MHI-headers-for-checked-CNSS2.patch')],cwd=t,check=True,capture_output=True)
        subprocess.run(['git','apply','--reverse',str(ROOT/'kernel/patches/popsicle/0057-checked-PEACH-CNSS2-remove-before-power-tail.patch')],cwd=t,check=True,capture_output=True)
        for f in FILES:
            if (t/f).read_bytes()!=subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+f]):raise ValueError('Unreviewed CNSS2 file: '+f)


def assemble(wlan):
    verify_platform_origin(wlan)
    pci=(wlan/'platform/cnss2/pci.c').read_text();pld=(wlan/'qcacld-3.0/core/pld/src/pld_pcie.c').read_text()
    header=(wlan/'platform/cnss2/main.h').read_text()
    f={'NATIVE_DEVICE_ID':'\n'.join(extract((wlan/'platform/cnss_utils/cnss_common.h').read_text(),r'^#define '+n+r'[^\n]*') for n in ['PEACH_DEVICE_ID','QCA6174_DEVICE_ID']),
       'NATIVE_ENUM':extract(header,r'^enum cnss_driver_state \{.*?^\};')+'\n'+extract(header,r'^enum cnss_driver_event_type \{.*?^\};'),
       'NATIVE_GUARD':extract((wlan/'platform/cnss2/pci.h').read_text(),r'^struct cnss_mishare_unregister_guard \{.*?^\};'),
       'NATIVE_PL_CALLBACKS':'\n'.join(native_function(pld,n) for n in ['pld_pcie_reinit','pld_pcie_shutdown','pld_pcie_idle_restart_cb','pld_pcie_idle_shutdown_cb']),
       'NATIVE_PL_REMOVE':native_function(pld,'pld_pcie_remove'),
       'NATIVE_PL_DESCRIPTOR':extract(pld,r'^static const struct mishare_wlan_pcie_execution_ops pld_pcie_execution = \{.*?^\};'),
       'NATIVE_PL_REGISTER':native_function(pld,'pld_pcie_register_driver'),
       'NATIVE_PL_CHECKED':native_function(pld,'pld_pcie_unregister_driver_checked'),
       'NATIVE_PL_UNREGISTER':native_function(pld,'pld_pcie_unregister_driver'),
       'NATIVE_COMMON_CHECKED':native_function((wlan/'qcacld-3.0/core/pld/src/pld_common.c').read_text(),'pld_unregister_driver_checked'),
       'NATIVE_HDD_CHECKED':native_function((wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_driver_ops.c').read_text(),'wlan_hdd_unregister_driver_checked'),
       'NATIVE_LATE_GUARD':extract((wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text(),r'/\* MISHARE_SSR_STOP_BEGIN:unload_checked_unregister \*/.*?/\* MISHARE_SSR_STOP_END:unload_checked_unregister \*/'),
       'NATIVE_REMOVE_INTERNAL':native_function(pci,'cnss_pci_call_driver_remove_internal'),
       'NATIVE_REMOVE_WRAPPER':native_function(pci,'cnss_pci_call_driver_remove'),
       'NATIVE_SHUTDOWN_INTERNAL':native_function(pci,'cnss_qca6290_shutdown_internal'),
       'NATIVE_SHUTDOWN_WRAPPER':native_function(pci,'cnss_qca6290_shutdown'),
       'NATIVE_LEGACY_HANDLER':native_function(pci,'cnss_pci_unregister_driver_hdlr'),
       'NATIVE_CHECKED_HANDLER':native_function(pci,'cnss_pci_unregister_driver_checked_hdlr'),
       'NATIVE_BUS_CHECKED':native_function((wlan/'platform/cnss2/bus.c').read_text(),'cnss_bus_unregister_driver_checked_hdlr'),
       'NATIVE_CHECKED_ENTRY':native_function(pci,'cnss_wlan_unregister_driver_checked_v1'),
       'NATIVE_LEGACY_ENTRY':native_function(pci,'cnss_wlan_unregister_driver'),
       'NATIVE_EVENT_ROUTE':extract((wlan/'platform/cnss2/main.c').read_text(),r'^\t\tcase CNSS_DRIVER_EVENT_UNREGISTER_DRIVER:.*?\n\t\t\tbreak;'),
    }
    # Extract only the five reviewed native slots; unrelated callbacks/ABI are
    # deliberately outside this userspace model.
    slots=extract(pld,r'^struct cnss_wlan_driver pld_pcie_ops = \{.*?^\};')
    fields=[]
    for name in ['remove','reinit','shutdown','idle_restart','idle_shutdown']:
        if name=='remove':fields.append(extract(slots,r'^\t\.remove\s*=[^\n]*'))
        else:fields.append(extract(slots,r'^#ifdef CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER\n\t\.'+name+r'\s*=.*?^#endif'))
    f['NATIVE_PL_SLOTS']='\n'.join(fields)
    # Declaration before event model uses this legacy dispatcher.
    code=BODY.replace('struct event_model {','static int cnss_bus_unregister_driver_hdlr(struct cnss_plat_data *p);\nstruct event_model {',1)
    for k,v in f.items():code=code.replace(k,v)
    return COMMON+code,f


def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,fragments=assemble(wlan);provider=(ROOT/'kernel/provider/execution.c').read_text();header=(ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for n in ['module.h','mutex.h','string.h']:(d/'linux'/n).write_text('/* modeled module API */\n')
        (d/'mishare_wlan_execution.h').write_bytes(header);(d/'execution.c').write_text(provider)
        source=d/'test.c';exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        def execute(c):
            source.write_text(c);subprocess.run(command,check=True)
            return subprocess.run([exe],text=True,capture_output=True,env=env,timeout=40)
        good=execute(code)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[]
        def mutate(key,old,new,marker):
            part=fragments[key];assert old in part
            changed=code.replace(part,part.replace(old,new,1),1);assert changed!=code;mutations.append((changed,marker))
        mutate('NATIVE_SHUTDOWN_INTERNAL','if (ret == -EAGAIN || (guard && ret))','if (ret == -EAGAIN)','EXPECTED_CNSS_PLATFORM_RETAINED')
        mutate('NATIVE_REMOVE_INTERNAL','if (ret)\n\t\t\t\treturn ret;','if (false && ret)\n\t\t\t\treturn ret;','EXPECTED_CNSS_NO_WLAN_TEARDOWN')
        mutate('NATIVE_PL_CHECKED','opairshare_wlan_execution_unregister_end(THIS_MODULE, ret)','opairshare_wlan_execution_unregister_end(THIS_MODULE, 0)','EXPECTED_CNSS_LATE_RETAINED')
        mutate('NATIVE_COMMON_CHECKED','ret = pld_pcie_unregister_driver_checked();\n\tif (ret)','ret = pld_pcie_unregister_driver_checked();\n\tif (false && ret)','EXPECTED_CNSS_LATE_RETAINED')
        mutate('NATIVE_LEGACY_ENTRY','if (test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL, &plat_priv->driver_state))','if (false && test_bit(CNSS_MISHARE_UNREGISTER_TERMINAL, &plat_priv->driver_state))','EXPECTED_CNSS_NO_LEGACY_BYPASS')
        mutate('NATIVE_CHECKED_ENTRY','CNSS_EVENT_SYNC_UNKILLABLE, &guard','0, &guard','EXPECTED_CNSS_SYNC_EVENT')
        for changed,marker in mutations:
            bad=execute(changed)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((marker,bad.returncode,bad.stderr[:1800]))
    report={'status':'MISHARE_CNSS_CHECKED_FIXTURE_PASS_ONLY','fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'execution_header_sha256':hashlib.sha256(header).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in fragments.items()},'platform_source_sha256':{f:hashlib.sha256((wlan/f).read_bytes()).hexdigest() for f in FILES},'success_cases':2,'isolated_failure_cases':9,'isolated_admission_cases':7,'negative_controls_rejected':len(mutations),'platform_origin_files_restored':11,'sanitizers':['address','undefined','leak detection'],'production_opt_in_consumer_executed':True,'default_build_opt_in_enabled':False,'CNSS2_binary_built':False,'phone_executed':False,'limitations':'Real provider, native PCIe register/checked unregister/remove, PLD/HDD refusal chain, CNSS2 checked/legacy entry, event routing, bus handler, complete native remove and qca6290 shutdown bodies. Five selected native ops slots and pthread synchronous event post; hardware/module/sync/HDD bodies are models. Only PEACH stable probed PCIe is admitted. Native power-tail errors retain remaining ownership but cannot undo already completed WLAN/MHI steps. Default consumer is unchanged; no real CNSS2 pair, ABI/KCFI, loader, RF, concurrent native power/recovery coordinator or module-exit veto is certified.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
