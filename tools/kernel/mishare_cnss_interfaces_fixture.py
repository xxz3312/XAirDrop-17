#!/usr/bin/env python3
"""Actions-only restored native interfaces; hardware/IRQ/component APIs modeled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_execution_fixture import extract

ROOT=Path(__file__).resolve().parents[2]
BODY=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
#define EXPORT_SYMBOL(x)
#define __iomem
#define BIT(n) (1UL<<(n))
#define cnss_pr_err(...) ((void)0)
#define cnss_pr_dbg(...) ((void)0)
#define cnss_pr_info(...) ((void)0)
#define do_div(n,b) ((n)/=(b))
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
#define IRQ_HANDLED 1
#define IRQ_WAKE_THREAD 2
#define IRQF_SHARED 1
#define IRQF_TRIGGER_RISING 2
#define IORESOURCE_MEM 1
typedef int irqreturn_t;
typedef uint64_t resource_size_t;
struct device_node {int id;};
struct device {struct device_node *of_node;void *data;};
struct platform_device {struct device dev;};
struct pci_dev {struct device dev;};
NATIVE_TYPES
NATIVE_CONSTANTS
struct cnss_plat_data {struct platform_device *plat_dev;struct cnss_wlan_tsf_info tsf_info;uint64_t fw_caps;unsigned int sku_features;};
struct cnss_pci_data {uint8_t smmu_s1_enable;};
struct component_ops {int (*bind)(struct device *,struct device *,void *);void (*unbind)(struct device *,struct device *,void *);};
static struct device_node node={1};
static struct platform_device pdev={{&node,NULL}},wonder_dev={{&node,NULL}};
static struct pci_dev pci_dev={{&node,NULL}};
static struct cnss_pci_data pci;
static struct cnss_plat_data plat;
static bool missing,has_property,has_resource,map_failure,early_irq;
static bool gpio_owned,irq_owned,component_owned;
static int gpio_error,irq_error,irq_value,gpio_frees,irq_frees,callbacks,component_adds,component_dels;
static uint64_t callback_time;
static void *callback_context;
static struct cnss_wlan_tsf_info *irq_cookie;
static irqreturn_t (*top_handler)(int,void *),(*thread_handler)(int,void *);
static uint32_t registers[3];
static char release_trace[8];static unsigned int release_at;
struct resource {resource_size_t start,size;};static struct resource resource={0x1000,12};
static struct cnss_plat_data *cnss_bus_dev_to_plat_priv(struct device *d){assert(d==&pdev.dev);return missing?NULL:&plat;}
#define to_pci_dev(d) container_of(d,struct pci_dev,dev)
static struct cnss_pci_data *cnss_get_pci_priv(struct pci_dev *p){assert(p==&pci_dev);return missing?NULL:&pci;}
static uint64_t cnss_get_host_timestamp(struct cnss_plat_data *p){assert(p==&plat);return 123456;}
static void *of_find_property(struct device_node *n,const char *key,void *len){assert(n==&node && !strcmp(key,TSF_SYNC_GPIO));(void)len;return has_property?&node:NULL;}
static int of_get_named_gpio(struct device_node *n,const char *key,int index){assert(n==&node && !strcmp(key,TSF_SYNC_GPIO) && !index);return 7;}
static struct resource *platform_get_resource_byname(struct platform_device *p,int type,const char *name){assert(p==&pdev && type==IORESOURCE_MEM && !strcmp(name,TSF_IRQ_TS));return has_resource?&resource:NULL;}
#define resource_size(r) ((r)->size)
static void *devm_ioremap(struct device *d,resource_size_t address,resource_size_t size){assert(d==&pdev.dev && address==0x1000 && size==12);return map_failure?NULL:registers;}
static uint32_t readl_relaxed(void *p){assert(p && (uintptr_t)p>=(uintptr_t)registers && (uintptr_t)p+4<=(uintptr_t)registers+sizeof(registers) && "EXPECTED_TSF_MMIO_BOUNDS");return *(uint32_t *)p;}
static int gpio_request(int n,const char *label){assert(n==7 && !strcmp(label,"wlan_tsf_gpio"));if(gpio_error)return gpio_error;if(gpio_owned)return -EBUSY;gpio_owned=true;return 0;}
static int gpio_direction_input(int n){assert(n==7 && gpio_owned);return 0;}
static int gpio_to_irq(int n){assert(n==7 && gpio_owned);return irq_value;}
static void gpio_free(int n){assert(n==7 && gpio_owned);gpio_owned=false;gpio_frees++;release_trace[release_at++]='G';}
static int request_threaded_irq(int n,irqreturn_t (*top)(int,void *),irqreturn_t (*thread)(int,void *),unsigned long flags,const char *label,void *ctx){
 assert(n==44 && gpio_owned && !irq_owned && flags==(IRQF_SHARED|IRQF_TRIGGER_RISING) && !strcmp(label,"wlan_tsf"));
 if(irq_error)return irq_error;
 irq_owned=true;irq_cookie=ctx;top_handler=top;thread_handler=thread;
 if(early_irq){assert(top(n,ctx)==IRQ_WAKE_THREAD);assert(thread(n,ctx)==IRQ_HANDLED && !callbacks);}
 return 0;
}
static void free_irq(int n,void *ctx){
 assert(n==44 && irq_owned && ctx==irq_cookie && "EXPECTED_TSF_IRQ_OWNERSHIP");
 assert(irq_cookie->context && irq_cookie->wlan_tsf_handler && "EXPECTED_TSF_DRAIN_CONTEXT");
 /* Simulate the last already admitted thread before the IRQ drain returns. */
 assert(thread_handler(n,ctx)==IRQ_HANDLED);
 irq_owned=false;irq_frees++;release_trace[release_at++]='F';
}
static void platform_set_drvdata(struct platform_device *p,void *data){assert(p==&wonder_dev);p->dev.data=data;}
static int component_add(struct device *d,const struct component_ops *ops){assert(d==&wonder_dev.dev && !component_owned && d->data);component_owned=true;component_adds++;return ops->bind(d,&pdev.dev,NULL);}
static void component_del(struct device *d,const struct component_ops *ops){assert(d==&wonder_dev.dev && component_owned && d->data);ops->unbind(d,&pdev.dev,NULL);component_owned=false;component_dels++;}
NATIVE_FUNCTIONS
NATIVE_WONDER
static void callback(void *ctx,uint64_t time){assert(ctx==&callback_context);callbacks++;callback_time=time;}
static void reset(void){
 assert(!gpio_owned && !irq_owned && !component_owned);
 memset(&plat,0,sizeof(plat));plat.plat_dev=&pdev;missing=has_property=has_resource=map_failure=early_irq=false;
 gpio_error=irq_error=gpio_frees=irq_frees=callbacks=component_adds=component_dels=0;irq_value=44;release_at=0;memset(release_trace,0,sizeof(release_trace));memset(registers,0,sizeof(registers));
 wonder_priv_data=NULL;wonder_plat_dev=NULL;wonder_dev.dev.data=NULL;callback_context=NULL;
}
static void timestamp_case(int kind){
 reset();has_property=true;assert(!cnss_get_wlan_tsf_gpio_info(&plat));
 if(kind){has_resource=true;assert(!cnss_get_tsf_ts_info(&plat));}
 early_irq=true;assert(!cnss_register_tsf_captured_handler(&pdev.dev,callback,&callback_context));
 assert(!callbacks && irq_owned && gpio_owned && "EXPECTED_TSF_REGISTER");
 uint64_t expected=123456;
 if(kind==1){registers[0]=BIT(0);registers[1]=1920;expected=100;}
 if(kind==2){registers[0]=0;registers[1]=1920;}
 if(kind==3){registers[0]=BIT(0)|BIT(8);registers[1]=1920;expected=100;}
 if(kind==4){registers[0]=BIT(0);registers[1]=0;}
 if(kind==5){registers[0]=BIT(0);registers[1]=UINT32_MAX;registers[2]=UINT32_MAX;expected=(UINT64_MAX/(TIME_CLOCK_FREQ_HZ/100000))*10;}
 assert(top_handler(44,irq_cookie)==IRQ_WAKE_THREAD);assert(thread_handler(44,irq_cookie)==IRQ_HANDLED);
 assert(callbacks==1 && callback_time==expected && "EXPECTED_TSF_TIMESTAMP");
 assert(cnss_wlan_tsf_capture_threaded_handler(43,irq_cookie)==IRQ_HANDLED && callbacks==1);
 assert(cnss_wlan_tsf_capture_threaded_handler(44,NULL)==IRQ_HANDLED);
 assert(!cnss_unregister_tsf_captured_handler(&pdev.dev,&callback_context));
 assert(!irq_owned && !gpio_owned && irq_frees==1 && gpio_frees==1 && "EXPECTED_TSF_DRAIN");
 assert(!strcmp(release_trace,"FG") && callbacks==2 && !plat.tsf_info.context && !plat.tsf_info.wlan_tsf_handler && "EXPECTED_TSF_DRAIN_ORDER");
}
static void failure_cases(void){
 for(int kind=0;kind<4;kind++){
  reset();has_property=true;assert(!cnss_get_wlan_tsf_gpio_info(&plat));
  if(kind==0)gpio_error=-EBUSY;
  if(kind==1)irq_value=-ENXIO;
  if(kind==2)irq_error=-ENOMEM;
  if(kind==3)plat.tsf_info.wlan_tsf_gpio=-EINVAL;
  assert(cnss_register_tsf_captured_handler(&pdev.dev,callback,&callback_context)==-EINVAL);
  assert(!irq_owned && !gpio_owned && !callbacks && "EXPECTED_TSF_FAILURE_ROLLBACK");
 }
 reset();assert(cnss_get_wlan_tsf_gpio_info(&plat)==-EINVAL && plat.tsf_info.irq_num==-EINVAL && plat.tsf_info.wlan_tsf_gpio==-EINVAL);
 has_resource=false;assert(cnss_get_tsf_ts_info(&plat)==-ENOMEM && !plat.tsf_info.irq_ts_info.is_valid_addr);
 has_resource=true;map_failure=true;assert(cnss_get_tsf_ts_info(&plat)==-ENOMEM && !plat.tsf_info.irq_ts_info.is_valid_addr);
 missing=true;assert(cnss_register_tsf_captured_handler(&pdev.dev,callback,&callback_context)==-EINVAL);assert(cnss_unregister_tsf_captured_handler(&pdev.dev,&callback_context)==-EINVAL);
}
static void wonder_cases(void){
 reset();assert(!cnss_set_vendor_wonder_priv_data(&callback_context));assert(!component_adds && wonder_priv_data==&callback_context && !wonder_plat_dev);
 assert(!cnss_vendor_wonder_dev_probe(&wonder_dev));assert(component_owned && component_adds==1 && wonder_dev.dev.data==&callback_context && "EXPECTED_WONDER_ATTACH");
 assert(cnss_vendor_wonder_dev_probe(&wonder_dev)==-EEXIST && component_adds==1);
 cnss_vendor_wonder_dev_remove();assert(!component_owned && component_dels==1 && !wonder_plat_dev && !wonder_priv_data && !wonder_dev.dev.data && "EXPECTED_WONDER_DETACH");
 reset();assert(!cnss_vendor_wonder_dev_probe(&wonder_dev));assert(!component_adds && !wonder_dev.dev.data);
 cnss_vendor_wonder_dev_remove();assert(!wonder_plat_dev && !wonder_priv_data);
 reset();assert(!cnss_vendor_wonder_dev_probe(&wonder_dev));assert(!cnss_set_vendor_wonder_priv_data(&callback_context));assert(component_owned);
 assert(!cnss_set_vendor_wonder_priv_data(NULL));assert(!component_owned && !wonder_dev.dev.data && component_dels==1 && "EXPECTED_WONDER_DETACH");cnss_vendor_wonder_dev_remove();
}
static void capability_cases(void){
 reset();missing=true;assert(!cnss_smmu_s1_enabled(&pci_dev.dev) && "EXPECTED_SMMU_QUERY");missing=false;pci.smmu_s1_enable=0;assert(!cnss_smmu_s1_enabled(&pci_dev.dev) && "EXPECTED_SMMU_QUERY");pci.smmu_s1_enable=1;assert(cnss_smmu_s1_enabled(&pci_dev.dev) && "EXPECTED_SMMU_QUERY");
 plat.fw_caps=QMI_WLFW_DIRECT_REFILL_SUPPORT_V01;
 assert(cnss_get_fw_cap(&pdev.dev,CNSS_FW_CAP_DIRECT_REFILL_SUPPORT) && "EXPECTED_DIRECT_REFILL_QUERY");
 plat.fw_caps=QMI_WLFW_BT_DUMP_OVER_WLAN_SUPPORT_V01;assert(!cnss_get_fw_cap(&pdev.dev,CNSS_FW_CAP_DIRECT_REFILL_SUPPORT) && "EXPECTED_DIRECT_REFILL_QUERY");
 assert(CNSS_FW_CAP_DIRECT_REFILL_SUPPORT==5 && QMI_WLFW_DIRECT_REFILL_SUPPORT_V01==0x80);
 plat.fw_caps=0;assert(!cnss_get_fw_cap(&pdev.dev,CNSS_FW_CAP_DIRECT_REFILL_SUPPORT));plat.fw_caps=0xff;missing=true;assert(!cnss_get_fw_cap(&pdev.dev,CNSS_FW_CAP_DIRECT_REFILL_SUPPORT));missing=false;assert(!cnss_get_fw_cap(&pdev.dev,(enum cnss_fw_caps)99));
}
int main(void){failure_cases();for(int k=0;k<6;k++)timestamp_case(k);wonder_cases();capability_cases();reset();puts("MISHARE_CNSS_INTERFACES_FIXTURE_PASS_ONLY");return 0;}
'''


def fn(s,n):return extract(s,r'^(?:static(?: inline)?\s+)?(?:int|void|bool|irqreturn_t) '+n+r'\([^;{]+?\)\s*\{.*?^\}')


def assemble(wlan):
    main=(wlan/'platform/cnss2/main.c').read_text();header=(wlan/'platform/cnss2/main.h').read_text();api=(wlan/'platform/inc/cnss2.h').read_text();pci=(wlan/'platform/cnss2/pci.c').read_text();qmi=(wlan/'platform/cnss_utils/wlan_firmware_service_v01.h').read_text()
    provenance=json.loads((ROOT/'docs/research/popsicle-cnss2-upstream-0127.json').read_text())
    f={n:fn(pci if n=='cnss_smmu_s1_enabled' else main,n) for n in provenance['upstream_function_sha256']}
    for n,h in provenance['upstream_function_sha256'].items():
        if hashlib.sha256(f[n].encode()).hexdigest()!=h:raise ValueError('Restored upstream function changed: '+n)
    f['cnss_pci_is_smmu_s1_enabled']=fn(pci,'cnss_pci_is_smmu_s1_enabled');f['cnss_get_fw_cap']=fn(main,'cnss_get_fw_cap')
    types=extract(api,r'^typedef void \(\*wlan_tsf_handler_t\)[^\n]*')+'\n'+extract(api,r'^enum cnss_fw_caps \{.*?^\};')
    types+='\n'+'\n'.join(extract(header,r'^struct '+n+r' \{.*?^\};') for n in ['cnss_irq_ts_info','cnss_wlan_tsf_info'])
    constants='\n'.join(extract(main,r'^#define '+n+r'[^\n]*') for n in ['TSF_SYNC_GPIO','TSF_IRQ_TS','TSF_IRQ_TS_OP_VALID','TSF_IRQ_TS_OP_OVERFLOW','TSF_IRQ_TS_OP_OFFSET','TSF_IRQ_TS_LO_OFFSET','TSF_IRQ_TS_HI_OFFSET'])
    constants+='\n'+extract(header,r'^#define TIME_CLOCK_FREQ_HZ[^\n]*')
    constants+='\n'+'\n'.join(extract(qmi,r'^#define '+n+r'[^\n]*') for n in ['QMI_WLFW_DIRECT_LINK_SKU_SUPPORT_V01','QMI_WLFW_CALDB_SEG_DDR_SUPPORT_V01','QMI_WLFW_WLAN_DUMP_OVER_BT_SUPPORT_V01','QMI_WLFW_BT_DUMP_OVER_WLAN_SUPPORT_V01','QMI_WLFW_DIRECT_REFILL_SUPPORT_V01'])
    # QMI constants use u64 in their original declarations.
    types='typedef uint64_t u64;typedef uint32_t u32;\n'+types
    a=main.index('/**\n * cnss_vendor_wonder_comp_bind');b=main.index('static int cnss_probe(',a);wonder=main[a:b]
    names=['cnss_get_wlan_tsf_gpio_info','cnss_get_tsf_ts_info','cnss_read_tsf_irq_ts','cnss_wlan_tsf_capture_threaded_handler','cnss_wlan_tsf_capture_irq_handler','cnss_wlan_tsf_init','cnss_wlan_tsf_deinit','cnss_register_tsf_captured_handler','cnss_unregister_tsf_captured_handler','cnss_pci_is_smmu_s1_enabled','cnss_smmu_s1_enabled','cnss_get_fw_cap']
    code=BODY.replace('NATIVE_TYPES',types).replace('NATIVE_CONSTANTS',constants).replace('NATIVE_FUNCTIONS','\n'.join(f[n] for n in names)).replace('NATIVE_WONDER',wonder)
    # Companion classification must precede interpreting its data as CNSS HDD.
    remove=main[main.index('static int cnss_remove('):];assert remove.index('device_id->driver_data == WONDER_VENDOR_DEVICE_ID')<remove.index('if (!plat_priv)')
    f.update({'types':types,'constants':constants,'wonder_block':wonder})
    return code,f


def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,fragments=assemble(wlan)
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);source=d/'test.c';exe=d/'test';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        def execute(c):
            source.write_text(c);subprocess.run(command,check=True)
            return subprocess.run([exe],capture_output=True,text=True,env=env,timeout=20)
        good=execute(code)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[]
        def mutate(key,old,new,marker):
            part=fragments[key];assert old in part
            changed=code.replace(part,part.replace(old,new,1),1);assert changed!=code;mutations.append((changed,marker))
        mutate('cnss_wlan_tsf_deinit','free_irq(tsf_info->irq_num, (void *)tsf_info);','if (false) free_irq(tsf_info->irq_num, (void *)tsf_info);','EXPECTED_TSF_DRAIN')
        mutate('cnss_wlan_tsf_deinit','if (tsf_info->irq_num >= 0)','tsf_info->context = NULL;\n\tif (tsf_info->irq_num >= 0)','EXPECTED_TSF_DRAIN_CONTEXT')
        mutate('cnss_wlan_tsf_init','gpio_free(tsf_info->wlan_tsf_gpio);','if (false) gpio_free(tsf_info->wlan_tsf_gpio);','EXPECTED_TSF_FAILURE_ROLLBACK')
        mutate('cnss_read_tsf_irq_ts','tsf_info->host_time_us = data_val;','tsf_info->host_time_us = 0;','EXPECTED_TSF_TIMESTAMP')
        mutate('wonder_block','component_del(&wonder_plat_dev->dev, &wonder_comp_ops);','if (false) component_del(&wonder_plat_dev->dev, &wonder_comp_ops);','EXPECTED_WONDER_DETACH')
        mutate('cnss_get_fw_cap','QMI_WLFW_DIRECT_REFILL_SUPPORT_V01','QMI_WLFW_BT_DUMP_OVER_WLAN_SUPPORT_V01','EXPECTED_DIRECT_REFILL_QUERY')
        mutate('cnss_smmu_s1_enabled','return cnss_pci_is_smmu_s1_enabled(pci_priv);','return !cnss_pci_is_smmu_s1_enabled(pci_priv);','EXPECTED_SMMU_QUERY')
        for changed,marker in mutations:
            bad=execute(changed)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((marker,bad.returncode,bad.stderr[:1500]))
    report={'status':'MISHARE_CNSS_INTERFACES_FIXTURE_PASS_ONLY','fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'native_fragments_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in fragments.items()},'exact_upstream_functions_checked':13,'timestamp_cases':6,'GPIO_IRQ_failure_cases':4,'wonder_success_lifecycles':3,'negative_controls_rejected':len(mutations),'sanitizers':['address','undefined','leak detection'],'phone_executed':False,'limitations':'Complete native restored functions against modeled GPIO/MMIO/IRQ/component/device lookup APIs. IRQ drain is a sequential admitted-callback model, not kernel concurrency. Preserves upstream timestamp conversion, caller-balanced TSF register/unregister and component semantics; no repeat-remove, concurrent publishers, failed component-add recovery, native loader or RF certification. Export CRCs and actual private layouts require the independent real paired build.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
