#!/usr/bin/env python3
"""Actions-only actual registration/load bodies; hardware and shutdown are models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from mishare_execution_fixture import COMMON, extract
from mishare_cnss_fixture import native_function, verify_platform_origin
ROOT=Path(__file__).resolve().parents[2]
BODY=r'''
#define CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER 1
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define module_param_named(...)
#define MODULE_PARM_DESC(...)
#define BIT(n) (1UL<<(n))
static bool test_bit(int n,const unsigned long *v){return !!(*v&BIT(n));}
static void set_bit(int n,unsigned long *v){*v|=BIT(n);}
#define cnss_pr_info(...) ((void)0)
#define cnss_pr_err(...) ((void)0)
#define cnss_pr_dbg(...) ((void)0)
#define cnss_pr_buf(...) ((void)0)
#define hdd_err(...) ((void)0)
#define hdd_nofl_info(...) ((void)0)
#define hdd_debug(...) ((void)0)
#define pr_info(...) ((void)0)
#define pld_err_rl(...) ((void)0)
#define CNSS_CHIP_VER_ANY 0
#define CNSS_EVENT_SYNC_UNKILLABLE 5
#define CNSS_TIMEOUT_CALIBRATION 1
#define msecs_to_jiffies(x) (x)
#define INIT_DELAYED_WORK(w,f) ((void)(w))
NATIVE_IDS
NATIVE_ENUM
struct pci_dev {struct device dev;};struct pci_device_id {int vendor,device;};
#include "execution.c"
struct cnss_wlan_driver {const struct pci_device_id *id_table;int chip_version;};
struct cnss_plat_data {
 unsigned long driver_state;void *bus_priv;int device_id;
 struct {int major_version;} device_version;bool cbc_enabled;
 struct cnss_wlan_driver *driver_ops;int wlan_reg_driver_work,power_up_complete;
 struct mutex driver_ops_lock;
};
struct cnss_pci_data {struct cnss_wlan_driver *driver_ops;int device_id;};
static struct cnss_plat_data plat={.driver_ops_lock={PTHREAD_MUTEX_INITIALIZER}};
static struct cnss_pci_data pci;
static const struct pci_device_id ids[]={{1,PEACH_DEVICE_ID},{0,0}};
static struct cnss_wlan_driver pld_pcie_ops={ids,2};
static bool missing_platform,loading_allowed=true,device_present=true;
static int event_error,registration_calls,event_calls,delayed_calls;
static struct cnss_plat_data *cnss_get_plat_priv_by_driver_ops(struct cnss_wlan_driver *p){assert(p==&pld_pcie_ops);registration_calls++;return missing_platform?NULL:&plat;}
static bool cnss_check_driver_loading_allowed(void){return loading_allowed;}
static bool pci_dev_present(const struct pci_device_id *p){assert(p==ids);return device_present;}
static unsigned int cnss_get_timeout(struct cnss_plat_data *p,int x){(void)p;(void)x;return 1;}
static void schedule_delayed_work(int *p,unsigned int x){(void)p;(void)x;delayed_calls++;}
static void reinit_completion(int *p){(void)p;}
static int cnss_driver_event_post(struct cnss_plat_data *p,int type,int flags,void *ops){
 assert(p==&plat && type==CNSS_DRIVER_EVENT_REGISTER_DRIVER && flags==CNSS_EVENT_SYNC_UNKILLABLE);
 pci.driver_ops=ops;event_calls++;return event_error;
}
NATIVE_CNSS_REGISTER
NATIVE_CNSS_CHECKED
static int cb_reinit(struct pci_dev *p,const struct pci_device_id *id){return 0;}
static void cb_shutdown(struct pci_dev *p){}
static int cb_idle(struct pci_dev *p){return 0;}
static const struct mishare_wlan_pcie_execution_ops pld_pcie_execution={.owner=THIS_MODULE,.reinit=cb_reinit,.shutdown=cb_shutdown,.idle_restart=cb_reinit,.idle_shutdown=cb_idle};
NATIVE_PCIE_STATE
NATIVE_PCIE_REGISTER
static int cleanup_error,rollback_calls,other_cleanup,cleanup_order,fail_bus;
static int pld_pcie_unregister_driver_checked(void){
 rollback_calls++;assert(!other_cleanup && "EXPECTED_ROLLBACK_FIRST");
 if(cleanup_error)return cleanup_error;
 assert(!opairshare_wlan_execution_unregister(THIS_MODULE));
 pld_pcie_execution_installed=pld_pcie_platform_retained=false;pci.driver_ops=NULL;return 0;
}
#define PLD_PCIE_REGISTERED BIT(0)
#define PLD_SNOC_REGISTERED BIT(1)
#define PLD_SDIO_REGISTERED BIT(2)
#define PLD_SNOC_FW_SIM_REGISTERED BIT(3)
#define PLD_PCIE_FW_SIM_REGISTERED BIT(4)
#define PLD_USB_REGISTERED BIT(5)
#define PLD_IPCI_REGISTERED BIT(6)
struct pld_driver_ops {void (*probe)(void),(*remove)(void),(*suspend)(void),(*resume)(void);};
static void cb(void){}
static struct pld_driver_ops hdd_ops={cb,cb,cb,cb};
struct pld_context {struct pld_driver_ops *ops;unsigned int pld_driver_state;};
static struct pld_context context;
static struct pld_context *pld_get_global_context(void){return &context;}
NATIVE_COMMON_HELPERS
static int pld_snoc_register_driver(void){return fail_bus==1?-EIO:0;}
static int pld_sdio_register_driver(void){return fail_bus==2?-EIO:0;}
static int pld_snoc_fw_sim_register_driver(void){return fail_bus==3?-EIO:0;}
static int pld_pcie_fw_sim_register_driver(void){return fail_bus==4?-EIO:0;}
static int pld_usb_register_driver(void){return fail_bus==5?-EIO:0;}
static int pld_ipci_register_driver(void){return fail_bus==6?-EIO:0;}
static void bus_cleanup(int n){assert(n<cleanup_order && "EXPECTED_REVERSE_BUS_CLEANUP");cleanup_order=n;other_cleanup++;}
static void pld_snoc_unregister_driver(void){bus_cleanup(1);}
static void pld_sdio_unregister_driver(void){bus_cleanup(2);}
static void pld_snoc_fw_sim_unregister_driver(void){bus_cleanup(3);}
static void pld_pcie_fw_sim_unregister_driver(void){bus_cleanup(4);}
static void pld_usb_unregister_driver(void){bus_cleanup(5);}
NATIVE_COMMON_REGISTER
static int complete_error,shared_cleanup,ctrl_error,load_calls,sleeps;
static void hdd_start_complete(int error){complete_error=error;}
NATIVE_HDD_STATE
static int wlan_hdd_register_driver(void){load_calls++;return pld_register_driver(&hdd_ops);}
#define HDD_MAX_PLD_REGISTER_RETRY 50
#define HDD_PLD_REGISTER_FAIL_SLEEP_DURATION 100
static void msleep(int duration){assert(duration==100);sleeps++;}
NATIVE_HDD_RETRY
/* Resource APIs are deterministic models. Each teardown is counted. */
#undef errno
#define QDF_STATUS int
#define QDF_IS_STATUS_ERROR(x) ((x)!=0)
#define QDF_IS_STATUS_SUCCESS(x) ((x)==0)
#define QDF_BUG(x) assert(x)
struct osif_driver_sync {int dummy;};static struct osif_driver_sync driver_sync;
static int wlan_wake_lock,con_mode,wlan_hdd_state_fops_ref;
static int hdd_qdf_init(void){return 0;}
static int qdf_status_to_os_return(int x){return x;}
static void osif_sync_init(void){}
static int osif_driver_sync_create_and_trans(struct osif_driver_sync **s){*s=&driver_sync;return 0;}
static int hdd_init(void){return 0;}
static int hdd_component_cb_init(void){return 0;}
static int hdd_component_init(void){return 0;}
static int qdf_wake_lock_create(int *p,const char *s){(void)p;(void)s;return 0;}
static void hdd_set_conparam(int x){(void)x;}
static int pld_init(void){return 0;}
static int pld_set_mode(int x){(void)x;return 0;}
static void hdd_driver_mode_change_register(void){}
static void osif_driver_sync_register(struct osif_driver_sync *s){(void)s;}
static void osif_driver_sync_trans_stop(struct osif_driver_sync *s){(void)s;}
static bool hdd_get_wlan_driver_status(void){return false;}
static int wlan_hdd_state_ctrl_param_create(void){return ctrl_error;}
static int wlan_hdd_tx_power_boost_dev_create(void){return 0;}
static void hdd_create_wifi_root_obj_sysfs_files(void){}
static void hdd_place_marker(void *a,const char *s,void *b){(void)a;(void)s;(void)b;}
static int wlan_hdd_unregister_driver_checked(void){return pld_pcie_unregister_driver_checked();}
static int osif_driver_sync_trans_start(struct osif_driver_sync **s){*s=&driver_sync;return 0;}
static void osif_driver_sync_unregister(void){shared_cleanup++;}
static void osif_driver_sync_wait_for_ops(struct osif_driver_sync *s){(void)s;shared_cleanup++;}
static void hdd_driver_mode_change_unregister(void){shared_cleanup++;}
static void pld_deinit(void){assert(!pld_registration_retained());shared_cleanup++;}
static int qdf_atomic_read(int *p){return *p;}
static void qdf_wake_lock_destroy(int *p){(void)p;shared_cleanup++;}
static void hdd_component_deinit(void){shared_cleanup++;}
static void hdd_component_cb_deinit(void){shared_cleanup++;}
static void hdd_deinit(void){shared_cleanup++;}
static void osif_driver_sync_destroy(struct osif_driver_sync *s){(void)s;shared_cleanup++;}
static void osif_sync_deinit(void){shared_cleanup++;}
static void hdd_qdf_deinit(void){shared_cleanup++;}
NATIVE_HDD_LOAD
NATIVE_HDD_INIT
static void setup(void){
 set_bit(CNSS_PCI_PROBE_DONE,&plat.driver_state);plat.bus_priv=&pci;plat.device_id=pci.device_id=PEACH_DEVICE_ID;plat.device_version.major_version=2;cleanup_order=7;
}
static void scenario(int kind){
 setup();
 if(kind==0){missing_platform=true;assert(hdd_module_init()==-EINVAL);assert(load_calls==50 && sleeps==49 && shared_cleanup==11 && !atomic_load(&wlan_module.refs) && "EXPECTED_CLEAN_RETRY");}
 else if(kind==1){event_error=-EAGAIN;assert(!hdd_module_init());assert(load_calls==1 && !sleeps && !shared_cleanup && mishare_load_error==-EAGAIN && "EXPECTED_QUARANTINE_NO_RETRY");}
 else if(kind>=2 && kind<=7){fail_bus=kind-1;assert(hdd_module_init()==-EINVAL);assert(rollback_calls==1 && other_cleanup==fail_bus-1 && !context.ops && !context.pld_driver_state && shared_cleanup==11 && !atomic_load(&wlan_module.refs) && "EXPECTED_BUS_ROLLBACK");}
 else if(kind>=8 && kind<=13){fail_bus=kind-7;cleanup_error=-EBUSY;assert(!hdd_module_init());assert(rollback_calls==1 && !other_cleanup && context.ops==&hdd_ops && context.pld_driver_state && !shared_cleanup && mishare_load_error==-EBUSY && "EXPECTED_FULL_GRAPH_RETAINED");}
 else if(kind==14){ctrl_error=-EIO;cleanup_error=-EINPROGRESS;assert(!hdd_module_init());assert(!shared_cleanup && mishare_load_error==-EINPROGRESS && "EXPECTED_LATE_LOAD_RETAINED");}
 else if(kind==15){assert(!hdd_module_init());assert(!mishare_load_error && pld_registration_retained() && atomic_load(&wlan_module.refs)==1 && "EXPECTED_SUCCESS_PINNED");}
 else if(kind==16){bool receipt=false;plat.cbc_enabled=true;assert(!cnss_wlan_register_driver_checked_v1(&pld_pcie_ops,&receipt));assert(receipt && delayed_calls==1 && pci.driver_ops==&pld_pcie_ops && !event_calls && "EXPECTED_DEFERRED_RECEIPT");}
 else if(kind==17){bool receipt=false;set_bit(CNSS_WLAN_HW_DISABLED,&plat.driver_state);assert(!cnss_wlan_register_driver_checked_v1(&pld_pcie_ops,&receipt));assert(receipt && plat.driver_ops==&pld_pcie_ops && !event_calls && "EXPECTED_HW_DEFERRED_RECEIPT");}
 else if(kind==18){device_present=false;assert(hdd_module_init()==-EINVAL);assert(!event_calls && !mishare_load_error && shared_cleanup==11 && !atomic_load(&wlan_module.refs) && "EXPECTED_CLEAN_REJECT");}
 if(mishare_load_error){
  int calls=load_calls,refs=atomic_load(&wlan_module.refs);assert(refs>=2 && pld_registration_retained() && "EXPECTED_RETAINED_PINS");
  assert(hdd_driver_load()==mishare_load_error && load_calls==calls && "EXPECTED_NO_REENTRY");
  assert(pld_registration_release_clean()==-EBUSY && atomic_load(&wlan_module.refs)==refs && "EXPECTED_NO_RELEASE");
 }
}
int main(void){
 (void)foreign_module;(void)module_is_live;
 for(int k=0;k<19;k++){pid_t p=fork();assert(p>=0);if(!p){scenario(k);_Exit(0);}int status;assert(waitpid(p,&status,0)==p && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_REGISTRATION_CHILD");}
 puts("MISHARE_REGISTRATION_FIXTURE_PASS_ONLY");return 0;
}
'''

def assemble(wlan):
    verify_platform_origin(wlan)
    pci=(wlan/'platform/cnss2/pci.c').read_text();pcie=(wlan/'qcacld-3.0/core/pld/src/pld_pcie.c').read_text();common=(wlan/'qcacld-3.0/core/pld/src/pld_common.c').read_text();hdd=(wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text()
    def tag(s,t):return extract(s,r'/\* MISHARE_SSR_STOP_BEGIN:'+t+r' \*/.*?/\* MISHARE_SSR_STOP_END:'+t+r' \*/')
    f={'NATIVE_IDS':'\n'.join(extract((wlan/'platform/cnss_utils/cnss_common.h').read_text(),r'^#define '+n+r'[^\n]*') for n in ['PEACH_DEVICE_ID','KIWI_DEVICE_ID','FIG_DEVICE_ID','QCA6174_DEVICE_ID']),
       'NATIVE_ENUM':extract((wlan/'platform/cnss2/main.h').read_text(),r'^enum cnss_driver_state \{.*?^\};')+'\n'+extract((wlan/'platform/cnss2/main.h').read_text(),r'^enum cnss_driver_event_type \{.*?^\};'),
       'NATIVE_CNSS_REGISTER':native_function(pci,'cnss_wlan_register_driver_internal'),
       'NATIVE_CNSS_CHECKED':native_function(pci,'cnss_wlan_register_driver_checked_v1'),
       'NATIVE_PCIE_STATE':tag(pcie,'reg_pcie_state'),
       'NATIVE_PCIE_REGISTER':native_function(pcie,'pld_pcie_register_driver'),
       'NATIVE_COMMON_HELPERS':tag(common,'reg_common_helpers'),
       'NATIVE_COMMON_REGISTER':native_function(common,'pld_register_driver'),
       'NATIVE_HDD_STATE':tag(hdd,'reg_hdd_state'),
       'NATIVE_HDD_RETRY':native_function(hdd,'hdd_register_driver_retry'),
       'NATIVE_HDD_LOAD':native_function(hdd,'hdd_driver_load'),
       'NATIVE_HDD_INIT':tag(hdd,'reg_hdd_module_init')}
    code=BODY
    for k,v in f.items():code=code.replace(k,v)
    # Linux's errno is a local identifier in these native functions.
    return COMMON+'\n#undef errno\n'+code,f

def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,f=assemble(wlan);provider=(ROOT/'kernel/provider/execution.c').read_bytes();header=(ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for n in ['module.h','mutex.h','string.h']:(d/'linux'/n).write_text('/* modeled APIs */\n')
        (d/'execution.c').write_bytes(provider);(d/'mishare_wlan_execution.h').write_bytes(header)
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(d/'test.c'),'-o',str(d/'test')]
        def execute(c):
            (d/'test.c').write_text(c);subprocess.run(command,check=True)
            return subprocess.run([d/'test'],capture_output=True,text=True,timeout=40,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))
        good=execute(code)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[('NATIVE_CNSS_REGISTER','*may_hold_wlan = true;','*may_hold_wlan = false;','EXPECTED_QUARANTINE_NO_RETRY'),
                   ('NATIVE_PCIE_REGISTER','pld_pcie_load_pin = true;','pld_pcie_load_pin = true; module_put(THIS_MODULE);','EXPECTED_EXEC_PUT_BALANCE'),
                   ('NATIVE_COMMON_REGISTER','if (cleanup)\n\t\treturn cleanup;','if (false && cleanup)\n\t\treturn cleanup;','EXPECTED_FULL_GRAPH_RETAINED'),
                   ('NATIVE_HDD_LOAD','if (pld_registration_retained())','if (false && pld_registration_retained())','pld_deinit'),
                   ('NATIVE_HDD_INIT','return 0; /* Resident quarantine; never announce functional success. */','return ret; /* deliberately unsafe init failure */','EXPECTED_QUARANTINE_NO_RETRY'),
                   ('NATIVE_HDD_RETRY','if (errno && pld_registration_retained())','if (false && errno && pld_registration_retained())','EXPECTED_QUARANTINE_NO_RETRY')]
        for key,old,new,marker in mutations:
            assert old in f[key];changed=code.replace(f[key],f[key].replace(old,new),1);assert changed!=code
            bad=execute(changed)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((key,bad.returncode,bad.stderr[:2000]))
    report={'status':'MISHARE_REGISTRATION_FIXTURE_PASS_ONLY','cases':19,'negative_controls_rejected':len(mutations),'fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider).hexdigest(),'execution_header_sha256':hashlib.sha256(header).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in f.items()},'phone_executed':False,'limitations':'Actual CNSS registration body/receipt, native PCIe registration, PLD registration rollback, full HDD load/retry/module-init bodies. Hardware/event publication, unload, resource helpers and Linux loader are models. Separate CNSS fixture covers actual checked unregister. No real module loader, RF, Apple interoperability or supported normal unload is certified.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
