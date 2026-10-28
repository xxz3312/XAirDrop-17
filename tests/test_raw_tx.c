// SPDX-License-Identifier: GPL-2.0-only
/* Runs the production WMA bridge against a modeled native transport. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "../kernel/popsicle-hdd/mishare_raw_protocol.h"
#define MISHARE_RAW_TEST
#define QDF_STATUS int
#define QDF_STATUS_SUCCESS 0
#define QDF_IS_STATUS_ERROR(x) ((x)!=0)
#define module_param(...)
#define MODULE_PARM_DESC(...)
#define QDF_MODULE_ID_WMA 1
#define QDF_MODULE_ID_QDF_DEVICE 2
#define WLAN_MGMT_NB_ID 3
#define WLAN_UMAC_COMP_MLME 4
#define GENERIC_NODOWLOAD_ACK_COMP_INDEX 5
#define QDF_STA_MODE 6
#define RATEID_6MBPS 7
#define GFP_KERNEL 0
#define BIT(n) (1U<<(n))
#define WRITE_ONCE(x,v) ((x)=(v))
#define READ_ONCE(x) (x)
#define msecs_to_jiffies(x) (x)
struct completion {int done;};
typedef int refcount_t;
static void refcount_set(refcount_t *r,int n) {*r=n;}
static bool refcount_dec_and_test(refcount_t *r) {assert(*r>0);return !--*r;}
static void init_completion(struct completion *c) {c->done=0;}
static void complete(struct completion *c) {assert(!c->done);c->done=1;}
static int live_contexts,live_packets,peer_refs,submit_calls,model,alloc_fail,missing_peer;
static void *model_alloc(size_t n,int flags) {(void)flags;void *p=calloc(1,n);assert(p);live_contexts++;return p;}
static void model_free(void *p) {assert(p && live_contexts);live_contexts--;free(p);}
#define kzalloc model_alloc
#define kfree model_free
struct wlan_objmgr_vdev {unsigned id;int mode,up,mlo;unsigned char mac[6];};
struct wlan_objmgr_peer {struct wlan_objmgr_vdev *vdev;};
struct packet {unsigned char bytes[2304];};
typedef struct packet *qdf_nbuf_t;
struct tx_send_params {unsigned frame_type,mcs_mask,nss_mask,preamble_type,bw_mask,retry_limit;};
struct wmi_mgmt_params {void *tx_frame;unsigned frm_len,vdev_id;unsigned char *pdata;void *qdf_ctx;unsigned tx_type,use_6mbps,tx_params_valid,chanfreq;struct tx_send_params tx_param;};
struct wma_model {unsigned max_bssid;struct {struct wlan_objmgr_vdev *vdev;unsigned ch_freq;} interfaces[4];void *psoc,*pdev;};
typedef struct wma_model *tp_wma_handle;
static struct wlan_objmgr_vdev vdev={1,QDF_STA_MODE,1,0,{2,1,2,3,4,5}},foreign;
static struct wlan_objmgr_peer peer={&vdev};
static struct wma_model wma={.max_bssid=4,.interfaces={[1]={&vdev,5180}},.psoc=(void*)1,.pdev=(void*)2};
static void *cds_get_context(int id) {return id==1?(void*)&wma:(void*)3;}
static int wma_validate_handle(tp_wma_handle p) {return !p;}
static unsigned wlan_vdev_get_id(struct wlan_objmgr_vdev *v) {return v->id;}
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) {return v->mode;}
static int wlan_vdev_mlme_is_mlo_vdev(struct wlan_objmgr_vdev *v) {return v->mlo;}
static int wlan_vdev_is_up_active_state(struct wlan_objmgr_vdev *v) {return v->up?0:1;}
static unsigned char *wlan_vdev_mlme_get_macaddr(struct wlan_objmgr_vdev *v) {return v->mac;}
static int wlan_objmgr_pdev_get_pdev_id(void *p) {(void)p;return 0;}
static struct wlan_objmgr_peer *wlan_objmgr_get_peer(void *p,int id,unsigned char *mac,int user) {(void)p;(void)id;(void)mac;(void)user;if(missing_peer)return NULL;peer_refs++;return &peer;}
static struct wlan_objmgr_vdev *wlan_peer_get_vdev(struct wlan_objmgr_peer *p) {return p->vdev;}
static void wlan_objmgr_peer_release_ref(struct wlan_objmgr_peer *p,int user) {(void)p;(void)user;assert(peer_refs);peer_refs--;}
static int cds_packet_alloc(uint16_t n,void **data,void **packet) {assert(n<=2304);if(alloc_fail)return 1;struct packet *p=calloc(1,sizeof(*p));assert(p);*data=p->bytes;*packet=p;live_packets++;return 0;}
static void cds_packet_free(qdf_nbuf_t p) {assert(p && live_packets);live_packets--;free(p);}
static void wma_update_tx_send_params(struct tx_send_params *p,int rate) {assert(rate==RATEID_6MBPS);p->frame_type=0;p->mcs_mask=16;p->nss_mask=1;p->preamble_type=1;}
static QDF_STATUS (*callback)(void*,qdf_nbuf_t,uint32_t,void*);
static void *callback_context;
static qdf_nbuf_t callback_packet;
static void fire(unsigned status) {assert(callback);void *ctx=callback_context;qdf_nbuf_t pkt=callback_packet;QDF_STATUS (*fn)(void*,qdf_nbuf_t,uint32_t,void*)=callback;callback=NULL;callback_context=NULL;callback_packet=NULL;assert(!fn(ctx,pkt,status,NULL));}
static int wlan_mgmt_txrx_mgmt_frame_tx(struct wlan_objmgr_peer *p,void *ctx,qdf_nbuf_t pkt,void *download,QDF_STATUS (*fn)(void*,qdf_nbuf_t,uint32_t,void*),int comp,struct wmi_mgmt_params *params) {
 assert(p==&peer && !download && comp==WLAN_UMAC_COMP_MLME && peer_refs==1);
 assert(params->tx_frame==pkt && params->pdata==pkt->bytes && params->vdev_id==1 && !params->chanfreq);
 assert(params->qdf_ctx==(void*)3 && params->tx_type==GENERIC_NODOWLOAD_ACK_COMP_INDEX);
 assert(params->tx_params_valid && params->tx_param.frame_type==1 && params->tx_param.mcs_mask==16 && params->tx_param.nss_mask==1 && params->tx_param.preamble_type==1 && params->tx_param.bw_mask==4 && params->tx_param.retry_limit==1);
 assert(mishare_raw_frame_valid(pkt->bytes,params->frm_len));submit_calls++;
 if(model==3)return 1;
 callback=fn;callback_context=ctx;callback_packet=pkt;
 if(model==1)fire(0);
 return 0;
}
static unsigned long wait_for_completion_timeout(struct completion *c,unsigned long timeout) {assert(timeout==1000);if(model==0)fire(7);return c->done?1:0;}
#include "../kernel/popsicle-hdd/wma_mishare_raw_tx.h"
int main(void) {
 unsigned char frame[34]={0x88};memset(frame+4,0xff,6);memcpy(frame+10,vdev.mac,6);frame[26]=0xaa;unsigned status=99;
 assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-EOPNOTSUPP && !submit_calls);
 mishare_raw_tx=true;
 assert(!mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status) && status==7 && !live_contexts && !live_packets && !peer_refs);
 model=1;assert(!mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status) && !status && !live_contexts && !live_packets);
 model=2;status=99;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-ETIMEDOUT && status==99 && live_contexts==1 && live_packets==1 && !peer_refs);
 fire(0);assert(!live_contexts && !live_packets && status==99);
 model=3;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-EIO && !live_contexts && !live_packets);
 alloc_fail=1;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-ENOMEM && !live_contexts && !live_packets && !peer_refs);alloc_fail=0;
 int calls=submit_calls;
 peer.vdev=&foreign;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-EXDEV && !peer_refs);peer.vdev=&vdev;
 missing_peer=1;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-ENOTCONN);missing_peer=0;
 vdev.mlo=1;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-EINVAL);vdev.mlo=0;
 assert(mishare_raw_tx_sync(&vdev,2412,frame,sizeof(frame),&status)==-EINVAL);
 frame[10]++;assert(mishare_raw_tx_sync(&vdev,5180,frame,sizeof(frame),&status)==-EINVAL);frame[10]--;
 frame[24]=0x80;assert(!mishare_raw_frame_valid(frame,sizeof(frame)));frame[24]=0;
 frame[1]=0x40;assert(!mishare_raw_frame_valid(frame,sizeof(frame)));frame[1]=0;
 frame[1]=2;assert(!mishare_raw_frame_valid(frame,sizeof(frame)));frame[1]=1;assert(mishare_raw_frame_valid(frame,sizeof(frame)));
 assert(submit_calls==calls && !live_contexts && !live_packets && !peer_refs);
 puts("RAW_NATIVE_SUBMIT_MODEL_PASS_ONLY");return 0;
}
