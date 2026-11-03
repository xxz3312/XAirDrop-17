#!/usr/bin/env python3
"""Actions-only native HTT constructor/register/HIF adapter into unmap parsing."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_htt_unmap_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
HTT=previous.HTT
INTERNAL='qca-wifi-host-cmn/dp/wifi3.0/dp_internal.h'
API='qca-wifi-host-cmn/htc/htc_api.h'
SERVICES='fw-api/fw/htc_services.h'
FW_HTC='fw-api/fw/htc.h'
PACKET='qca-wifi-host-cmn/htc/htc_packet.h'
HTT_HEADER='qca-wifi-host-cmn/dp/wifi3.0/dp_htt.h'
NAMES=['htt_soc_initialize','htt_htc_soc_attach','dp_htt_hif_t2h_hp_callback','dp_htt_h2t_full']
def native(root,name):
 text=(root/HTT).read_text()
 pattern=r'(?:static\s+)?(?:QDF_STATUS|enum htc_send_full_action|void\s*\*)\s*'+name+r'\s*\([^;{]+\)\s*\{.*?^\}'
 return re.search(pattern,text,re.S|re.M)[0]
def hif_variants(root):
 result=re.findall(r'static inline void\s+dp_hif_update_pipe_callback\s*\([^;{]+\)\s*\{.*?^\}',(root/INTERNAL).read_text(),re.S|re.M)
 assert len(result)==2 and 'hif_update_pipe_callback(dp_soc->hif_handle' in result[0] and 'hif_update_pipe_callback(' not in result[1].split('{',1)[1]
 return result

def entry_prefix(root):
 body=extract((root/HTT).read_text(),'dp_htt_t2h_msg_handler')
 return body[:body.index('\thtt_t2h_msg = (qdf_nbuf_t)pkt->pPktContext;')]

def define(text,name):
 return re.search(r'^#define '+re.escape(name)+r'\b(?:[^\n]*\\\n)*[^\n]*',text,re.M)[0]
SUPPORT=r'''
NATIVE_CONSTANTS
struct cdp_ctrl_objmgr_psoc {int token;};
typedef void *HTC_HANDLE;
typedef void *hal_soc_handle_t;
typedef void *qdf_device_t;
struct htc_ep_callbacks {
 void *pContext;
 void (*EpTxComplete)(void *,HTC_PACKET *);
 void *EpTxCompleteMultiple;
 void (*EpRecv)(void *,HTC_PACKET *);
 void *EpRecvRefill;
 enum htc_send_full_action (*EpSendFull)(void *,HTC_PACKET *);
 int RecvRefillWaterMark;
};
struct htc_service_connect_req {unsigned service_id,ConnectionFlags;void *pMetaData;unsigned MetaDataLength;struct htc_ep_callbacks EpCallbacks;int MaxSendQueueDepth;unsigned LocalConnectionFlags,MaxSendMsgSize;};
struct htc_service_connect_resp {void *pMetaData;unsigned BufferLength,ActualLength,Endpoint,MaxMsgLength,ConnectRespCode;};
struct hif_msg_callbacks {QDF_STATUS (*rxCompletionHandler)(void *,qdf_nbuf_t,uint8_t);void *Context;void *txCompletionHandler;};
static struct htc_service_connect_req h100_request;
static struct hif_msg_callbacks h100_pipe;
static struct cdp_ctrl_objmgr_psoc h100_ctrl;
static int h100_htc_token,h100_hal_token,h100_os_token,h100_hif_token;
static bool h100_prepared,h100_connected,h100_published,h100_wdi=true,h100_hp,h100_in_hp,h100_hp_zeroed,h100_allow_null;
static unsigned h100_stage,h100_dispatches,h100_pipe_asserts,h100_endpoint=6,h100_connects,h100_updates;
static bool h100_req_zero,h100_resp_zero;
static QDF_STATUS h100_connect_status;
static qdf_nbuf_t h100_expected_nbuf;
void h100_dispatch(void *,HTC_PACKET *);
QDF_STATUS dp_htt_hif_t2h_hp_callback(void *,qdf_nbuf_t,uint8_t);
enum htc_send_full_action dp_htt_h2t_full(void *,HTC_PACKET *);
static void h100_tx_complete(void *ctx,HTC_PACKET *pkt) {(void)ctx;(void)pkt;assert(!"unselected native TX completion");}
static void h100_pipe_assert(bool value) {assert(value && "EXPECTED_NATIVE_HP_PIPE");h100_pipe_asserts++;}
static void h100_zero(void *p,size_t n) {
 if(h100_in_hp){assert(h100_pipe_asserts==1 && "EXPECTED_HP_PIPE_ASSERT_BEFORE_ZERO");assert(n==sizeof(HTC_PACKET));h100_hp_zeroed=true;}
 else if(!h100_stage){assert(n==sizeof(struct htc_service_connect_req));h100_req_zero=true;h100_stage=1;}
 else {assert(h100_stage==1 && n==sizeof(struct htc_service_connect_resp));h100_resp_zero=true;h100_stage=2;}
 memset(p,0,n);
}
static QDF_STATUS h100_connect(void *handle,struct htc_service_connect_req *req,struct htc_service_connect_resp *resp) {
 assert(handle==&h100_htc_token && h100_stage==2 && h100_req_zero && h100_resp_zero && !h100_connects);h100_connects++;
 assert(req->EpCallbacks.pContext==&h99_soc && "EXPECTED_NATIVE_RX_CONTEXT");
 assert(req->EpCallbacks.EpRecv==h100_dispatch && "EXPECTED_NATIVE_RX_CALLBACK");
 assert(req->EpCallbacks.EpTxComplete==h100_tx_complete && !req->EpCallbacks.EpTxCompleteMultiple && !req->EpCallbacks.EpRecvRefill && req->EpCallbacks.RecvRefillWaterMark==1 && req->EpCallbacks.EpSendFull==dp_htt_h2t_full);
 assert(!req->pMetaData && !req->MetaDataLength && req->MaxSendQueueDepth==64 && req->ConnectionFlags==8 && req->service_id==0x300 && !req->LocalConnectionFlags && !req->MaxSendMsgSize && "EXPECTED_NATIVE_SERVICE_CONTRACT");
 assert(h100_endpoint>0 && h100_endpoint<(unsigned)ENDPOINT_MAX);h100_request=*req;
 if(h100_connect_status!=QDF_STATUS_SUCCESS){return h100_connect_status;}
 resp->Endpoint=h100_endpoint;h100_published=true;return QDF_STATUS_SUCCESS;
}
static void h100_save_endpoint(void *hif,unsigned endpoint) {
 assert(h100_connect_status==QDF_STATUS_SUCCESS && h100_published && "EXPECTED_FAILED_CONNECT_NO_PUBLICATION");
 assert(hif==&h100_hif_token && h100_stage==2 && endpoint==h100_endpoint && h99_soc.htc_endpoint==h100_endpoint && "EXPECTED_NATIVE_ENDPOINT_RESPONSE");h100_stage=3;
}
static void h100_logging_init(void **logger,void *ctrl) {assert(h100_stage==3 && logger==&h99_soc.htt_logger_handle && ctrl==&h100_ctrl);*logger=&h99_soc;h100_stage=4;}
static void h100_hif_store(void *handle,uint8_t pipe,struct hif_msg_callbacks *callbacks) {
 assert(handle==&h100_hif_token && pipe==5 && h100_stage==4 && !h100_pipe.rxCompletionHandler);
 assert(callbacks->Context==&h99_soc && "EXPECTED_NATIVE_HIF_CONTEXT");
 assert(callbacks->rxCompletionHandler==dp_htt_hif_t2h_hp_callback && !callbacks->txCompletionHandler && "EXPECTED_NATIVE_HIF_CALLBACK");h100_pipe=*callbacks;
}
HIF_ON_BLOCK
HIF_OFF_BLOCK
static void h100_update(struct dp_soc *s,void *ctx,QDF_STATUS (*cb)(void *,qdf_nbuf_t,uint8_t),uint8_t pipe) {
 assert(s==&d96_soc && ctx==&h99_soc && "EXPECTED_NATIVE_HIF_CONTEXT");assert(cb==dp_htt_hif_t2h_hp_callback && pipe==5 && h100_stage==4);h100_updates++;
 if(h100_wdi){h100_hif_on(s,ctx,cb,pipe);assert(h100_pipe.rxCompletionHandler==cb && h100_pipe.Context==ctx);}
 else {h100_hif_off(s,ctx,cb,pipe);assert(!h100_pipe.rxCompletionHandler && !h100_pipe.Context);}
 h100_stage=5;
}
static bool h100_gate(void *context,HTC_PACKET *pkt) {
 assert(h100_connected && (context==&h99_soc || (h100_allow_null && !context)) && "EXPECTED_NATIVE_DELIVERY_CONTEXT");
 if(h100_in_hp){assert(h100_hp_zeroed && h100_pipe_asserts==1 && "EXPECTED_HP_ZEROED_PACKET");assert(pkt && pkt->Status==QDF_STATUS_SUCCESS && "EXPECTED_HP_SUCCESS_PACKET");assert(pkt->pPktContext==h100_expected_nbuf && "EXPECTED_HP_NBUF_CONTEXT");}
 h100_dispatches++;return dp_htt_t2h_peer_unmap_try_handle(context,pkt);
}
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
ENTRY_MACROS
NATIVE_ENTRY_PREFIX
 assert(!"UNSELECTED_HTT_GENERIC_PATH");
}
ENTRY_UNMACROS
#pragma GCC diagnostic pop
NATIVE_FULL
HP_MACROS
NATIVE_HP
HP_UNMACROS
ATTACH_MACROS
NATIVE_ATTACH
ATTACH_UNMACROS
NATIVE_INITIALIZE
static void h100_prepare(void) {
 assert(!h100_prepared);h100_prepared=true;h100_stage=h100_dispatches=h100_pipe_asserts=h100_connects=h100_updates=0;h100_connected=h100_published=h100_req_zero=h100_resp_zero=h100_in_hp=h100_hp_zeroed=false;h100_connect_status=QDF_STATUS_SUCCESS;
 memset(&h100_request,0,sizeof(h100_request));memset(&h100_pipe,0,sizeof(h100_pipe));
 d96_soc.hif_handle=&h100_hif_token;h99_soc.dp_soc=&d96_soc;h99_soc.htt_logger_handle=NULL;h99_soc.htc_endpoint=255;
 h99_soc.ctrl_psoc=h99_soc.htc_soc=h99_soc.hal_soc=h99_soc.osdev=NULL;
}
static void *h100_construct(void) {return htt_soc_initialize(&h99_soc,&h100_ctrl,&h100_htc_token,&h100_hal_token,&h100_os_token);}
static void h100_ensure(void) {
 if(h100_connected){return;}
 if(!h100_prepared){h100_prepare();}
 assert(h100_construct()==&h99_soc && "EXPECTED_NATIVE_INITIALIZE_SUCCESS");
 assert(h100_stage==5 && h100_connects==1 && h100_updates==1 && h100_published && h99_soc.htc_endpoint==h100_endpoint && h99_soc.ctrl_psoc==&h100_ctrl && h99_soc.htc_soc==&h100_htc_token && h99_soc.hal_soc==&h100_hal_token && h99_soc.osdev==&h100_os_token && "EXPECTED_NATIVE_INITIALIZE_HANDLES");h100_connected=true;
}
static void h100_deliver(HTC_PACKET *pkt) {
 assert(h100_connected && h100_published);unsigned before=h100_dispatches;h100_in_hp=h100_hp;h100_pipe_asserts=0;h100_hp_zeroed=false;h100_expected_nbuf=pkt?(qdf_nbuf_t)pkt->pPktContext:NULL;
 if(h100_hp){assert(h100_wdi && h100_pipe.rxCompletionHandler && h100_pipe.Context==&h99_soc);assert(h100_pipe.rxCompletionHandler(h100_pipe.Context,h100_expected_nbuf,5)==QDF_STATUS_SUCCESS && "EXPECTED_NATIVE_HP_STATUS");}
 else {h100_request.EpCallbacks.EpRecv(h100_request.EpCallbacks.pContext,pkt);}
 assert(h100_dispatches==before+1 && "EXPECTED_NATIVE_RECEIVE_DISPATCH");h100_in_hp=false;
}
static void h100_packet_contract(bool wdi,bool hp,unsigned endpoint,unsigned type,unsigned offset,QDF_STATUS status) {
 h100_enabled=h99_probe=true;h100_wdi=wdi;h100_hp=hp;h100_endpoint=endpoint;h100_ensure();
 struct h99_nbuf b;uint8_t mac[6]={0x12,0x34,0x56,0x78,0x9a,0xbc};h99_build(&b,type,42,7,1,0x1234,mac,type==0x04?4:20,offset);h99_expected_calls=status==QDF_STATUS_SUCCESS;
 HTC_PACKET pkt={.pPktContext=&b,.Status=status};assert(h100_request.EpCallbacks.EpSendFull(&h99_soc,&pkt)==0 && b.live && !h99_frees);
 unsigned errors=h99_soc.stats.htc_err_cnt;h100_deliver(&pkt);
 assert(!b.live && h99_frees==1 && h99_calls==h99_expected_calls && h99_soc.stats.htc_err_cnt==errors+(unsigned)(status!=QDF_STATUS_SUCCESS && status!=QDF_STATUS_E_CANCELED) && "EXPECTED_NATIVE_CALLBACK_OWNERSHIP");
}
static void h100_failure(QDF_STATUS status,bool wdi) {
 h100_enabled=true;h100_wdi=wdi;h100_prepare();h100_connect_status=status;assert(!h100_construct() && "EXPECTED_NATIVE_INITIALIZE_FAILURE");
 assert(h100_stage==2 && h100_connects==1 && !h100_published && !h100_connected && !h100_updates && !h100_pipe.rxCompletionHandler && h99_soc.htc_endpoint==255 && !h99_soc.htt_logger_handle && "EXPECTED_FAILED_CONNECT_NO_PUBLICATION");
}
static void h100_edge(unsigned mode) {
 h100_enabled=h99_probe=true;h100_wdi=true;h100_ensure();h100_in_hp=mode==1 || mode==2;h100_pipe_asserts=0;h100_hp_zeroed=false;
 if(mode==0){h100_request.EpCallbacks.EpRecv(&h99_soc,NULL);}
 else if(mode==1){h100_expected_nbuf=NULL;assert(h100_pipe.rxCompletionHandler(&h99_soc,NULL,5)==QDF_STATUS_SUCCESS);}
 else if(mode==2){struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,0x04,42,7,0,0,mac,4,0);h99_expected_calls=0;h100_expected_nbuf=&b;h100_allow_null=true;assert(h100_pipe.rxCompletionHandler(NULL,&b,5)==QDF_STATUS_SUCCESS && !b.live && h99_frees==1);}
 else {HTC_PACKET pkt={.pPktContext=NULL,.Status=QDF_STATUS_SUCCESS};h100_request.EpCallbacks.EpRecv(&h99_soc,&pkt);}
 assert(h100_dispatches==1);
}
static void h100_bad_pipe(void) {
 h100_enabled=h99_probe=true;h100_wdi=true;h100_ensure();struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,0x04,42,7,0,0,mac,4,0);h99_expected_calls=1;h100_in_hp=true;h100_pipe_asserts=0;h100_hp_zeroed=false;h100_expected_nbuf=&b;
 h100_pipe.rxCompletionHandler(&h99_soc,&b,4);assert(!"EXPECTED_BAD_PIPE_REJECTION");
}
static void h100_contracts(void) {
 unsigned count=0;
 for(unsigned wdi=0;wdi<2;wdi++){for(unsigned endpoint=0;endpoint<2;endpoint++){for(unsigned status=0;status<3;status++){for(unsigned fmt=0;fmt<2;fmt++){for(unsigned offset=0;offset<2;offset++){
  pid_t c=fork();assert(c>=0);if(!c){h100_packet_contract(wdi,false,endpoint?6:3,fmt?0x1f:0x04,offset,status==0?QDF_STATUS_SUCCESS:status==1?QDF_STATUS_E_FAILURE:QDF_STATUS_E_CANCELED);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}}}}
 for(unsigned endpoint=0;endpoint<2;endpoint++){for(unsigned fmt=0;fmt<2;fmt++){for(unsigned offset=0;offset<2;offset++){
  pid_t c=fork();assert(c>=0);if(!c){h100_packet_contract(true,true,endpoint?6:3,fmt?0x1f:0x04,offset,QDF_STATUS_SUCCESS);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}}
 for(unsigned wdi=0;wdi<2;wdi++){for(unsigned fail=0;fail<2;fail++){
  pid_t c=fork();assert(c>=0);if(!c){h100_failure(fail?QDF_STATUS_E_BUSY:QDF_STATUS_E_FAILURE,wdi);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}
 for(unsigned mode=0;mode<4;mode++){
  pid_t c=fork();assert(c>=0);if(!c){h100_edge(mode);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }
 assert(count==64);
}
'''
def fixture(root):
 s,exits,stubbed=previous.fixture(root);text=(root/HTT).read_text();api=(root/API).read_text();services=(root/SERVICES).read_text()
 constants='\n'.join([re.search(r'enum htc_send_full_action \{.*?^\};',api,re.S|re.M)[0],re.search(r'typedef enum \{.*?\} HTC_ENDPOINT_ID;', (root/PACKET).read_text(),re.S)[0],re.search(r'typedef enum \{.*?\}HTC_SERVICE_GROUP_IDS;',services,re.S)[0],define(services,'MAKE_SERVICE_ID'),define(services,'HTT_DATA_MSG_SVC'),define((root/FW_HTC).read_text(),'HTC_CONNECT_FLAGS_DISABLE_CREDIT_FLOW_CTRL'),define((root/HTT_HEADER).read_text(),'DP_HTT_MAX_SEND_QUEUE_DEPTH'),define((root/INTERNAL).read_text(),'DP_HTT_T2H_HP_PIPE')])
 s=owner.replace_once(s,'struct dp_soc {','struct dp_soc {void *hif_handle;')
 s=owner.replace_once(s,'struct htt_soc {struct dp_soc *dp_soc;void *htt_logger_handle;struct {unsigned htc_err_cnt;} stats;};','struct htt_soc {struct dp_soc *dp_soc;void *htt_logger_handle,*ctrl_psoc,*htc_soc,*hal_soc,*osdev;unsigned htc_endpoint;struct {unsigned htc_err_cnt;} stats;};')
 s=owner.replace_once(s,'static struct htt_soc h99_soc;','static struct htt_soc h99_soc;\nstatic bool h100_enabled;\nstatic void h100_ensure(void);\nstatic void h100_deliver(HTC_PACKET *);')
 s=owner.replace_once(s,'h99_soc.dp_soc=&d96_soc;h99_soc.htt_logger_handle=&h99_soc;','if(!h100_enabled){h99_soc.dp_soc=&d96_soc;h99_soc.htt_logger_handle=&h99_soc;}')
 body=function(s,'h99_unmap');updated=owner.replace_once(body,'uint8_t golden[6]','if(h100_enabled){h100_ensure();}\n uint8_t golden[6]');needle='assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt) && !b.live'
 updated=owner.replace_once(updated,needle,'if(h100_enabled){h100_deliver(&pkt);}else{assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt));}\n assert(!b.live')
 s=owner.replace_once(s,body,updated)
 block=SUPPORT.replace('\nNATIVE_CONSTANTS\n','\n'+constants+'\n')
 def scoped(body,mapping):
  start,end=previous.previous.macros(mapping);return start+'\n'+body+'\n'+end
 variants=hif_variants(root)
 block=block.replace('\nHIF_ON_BLOCK\n','\n'+scoped(variants[0],{'dp_hif_update_pipe_callback':'h100_hif_on','hif_update_pipe_callback':'h100_hif_store'})+'\n').replace('\nHIF_OFF_BLOCK\n','\n'+scoped(variants[1],{'dp_hif_update_pipe_callback':'h100_hif_off','hif_update_pipe_callback':'h100_hif_store'})+'\n')
 for token,mapping in [('ENTRY',{'dp_htt_t2h_msg_handler':'h100_dispatch','dp_htt_t2h_peer_unmap_try_handle':'h100_gate'}),('HP',{'qdf_assert_always':'h100_pipe_assert','qdf_mem_zero':'h100_zero','dp_htt_t2h_msg_handler':'h100_dispatch'}),('ATTACH',{'qdf_mem_zero':'h100_zero','htc_connect_service':'h100_connect','dp_htt_h2t_send_complete':'h100_tx_complete','dp_htt_t2h_msg_handler':'h100_dispatch','hif_save_htc_htt_config_endpoint':'h100_save_endpoint','htt_interface_logging_init':'h100_logging_init','dp_hif_update_pipe_callback':'h100_update'})]:
  start,end=previous.previous.macros(mapping);block=block.replace('\n'+token+'_MACROS\n','\n'+start+'\n').replace('\n'+token+'_UNMACROS\n','\n'+end+'\n')
 for token,body in [('NATIVE_ENTRY_PREFIX',entry_prefix(root)),('NATIVE_FULL',native(root,NAMES[3])),('NATIVE_HP',native(root,NAMES[2])),('NATIVE_ATTACH',native(root,NAMES[1])),('NATIVE_INITIALIZE',native(root,NAMES[0]))]:block=block.replace('\n'+token+'\n','\n'+body+'\n')
 anchor=function(s,'h99_contracts');s=owner.replace_once(s,anchor,anchor+'\n'+block)
 case=function(s,'p92_case');s=owner.replace_once(s,case,owner.replace_once(case,'h99_enabled=true;','h100_enabled=true;h99_enabled=true;'))
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++){for(unsigned route=0;route<3;route++){for(unsigned fmt=0;fmt<2;fmt++){for(unsigned offset=0;offset<2;offset++){
  pid_t c=fork();assert(c>=0);if(!c){h100_wdi=route!=2;h100_hp=route==1;h99_v2=fmt;h99_unaligned=offset;d98_probes=true;d98_txrx=true;d98_ol=true;d98_partner_enabled=true;d97_extra=2;d97_rx=true;d97_reverse=trace;d96_extra=2;d96_notify_enabled=true;p92_case(trace,1,0,false);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}}}
 assert(count==192);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==168);','assert(count==168);\n'+extra))
 main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'h99_contracts();','h99_contracts();h100_contracts();'))
 for n in NAMES:assert s.count(native(root,n))==1
 for body in variants:assert s.count(body)==1
 assert s.count(entry_prefix(root))==1
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 old=owner.replace_once(source,'h100_enabled=true;h99_enabled=true;','h100_enabled=false;h99_enabled=true;');previous.negative_controls(directory,c_file,command,env,old,root);exe=directory/'engine'
 controls=[
 ('rx_context',NAMES[1],'connect.EpCallbacks.pContext = soc;','connect.EpCallbacks.pContext = NULL;','h100_packet_contract(true,false,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_RX_CONTEXT'),
 ('rx_callback',NAMES[1],'connect.EpCallbacks.EpRecv = dp_htt_t2h_msg_handler;','connect.EpCallbacks.EpRecv = NULL;','h100_packet_contract(true,false,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_RX_CALLBACK'),
 ('hif_context',NAMES[1],'dp_hif_update_pipe_callback(soc->dp_soc, (void *)soc,','dp_hif_update_pipe_callback(soc->dp_soc, NULL,','h100_packet_contract(true,true,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_HIF_CONTEXT'),
 ('endpoint',NAMES[1],'soc->htc_endpoint = response.Endpoint;','soc->htc_endpoint = 0;','h100_packet_contract(true,false,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_ENDPOINT_RESPONSE'),
 ('connect_failure',NAMES[1],'if (status != QDF_STATUS_SUCCESS)','if (false && status != QDF_STATUS_SUCCESS)','h100_failure(QDF_STATUS_E_FAILURE,true);','EXPECTED_FAILED_CONNECT_NO_PUBLICATION'),
 ('credits',NAMES[1],'connect.ConnectionFlags |= HTC_CONNECT_FLAGS_DISABLE_CREDIT_FLOW_CTRL;','connect.ConnectionFlags |= 0;','h100_packet_contract(true,false,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_SERVICE_CONTRACT'),
 ('hif_callback','HIF_ON','hif_pipe_callbacks.rxCompletionHandler = callback;','hif_pipe_callbacks.rxCompletionHandler = NULL;','h100_packet_contract(true,true,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_HIF_CALLBACK'),
 ('hif_stored_context','HIF_ON','hif_pipe_callbacks.Context = cb_context;','hif_pipe_callbacks.Context = NULL;','h100_packet_contract(true,true,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_NATIVE_HIF_CONTEXT'),
 ('hp_pipe',NAMES[2],'qdf_assert_always(pipe_id == DP_HTT_T2H_HP_PIPE);','/* omit pipe admission */','h100_bad_pipe();','EXPECTED_HP_PIPE_ASSERT_BEFORE_ZERO'),
 ('hp_status',NAMES[2],'htc_pkt.Status = QDF_STATUS_SUCCESS;','htc_pkt.Status = QDF_STATUS_E_FAILURE;','h100_packet_contract(true,true,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_HP_SUCCESS_PACKET'),
 ('hp_nbuf',NAMES[2],'htc_pkt.pPktContext = (void *)nbuf;','htc_pkt.pPktContext = NULL;','h100_packet_contract(true,true,6,0x04,0,QDF_STATUS_SUCCESS);','EXPECTED_HP_NBUF_CONTEXT'),
 ('entry_gate','PREFIX','if (dp_htt_t2h_peer_unmap_try_handle(context, pkt))','if (false && dp_htt_t2h_peer_unmap_try_handle(context, pkt))','h100_packet_contract(true,false,6,0x04,0,QDF_STATUS_SUCCESS);','UNSELECTED_HTT_GENERIC_PATH'),
 ('constructor_failure',NAMES[0],'return NULL;','return soc;','h100_failure(QDF_STATUS_E_FAILURE,true);','EXPECTED_NATIVE_INITIALIZE_FAILURE'),
 ]
 for label,name,needle,mutation,call,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {'+call+'_Exit(0);}')
  body=hif_variants(root)[0] if name=='HIF_ON' else entry_prefix(root) if name=='PREFIX' else native(root,name)
  c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])
 target=owner.replace_once(source,function(source,'main'),'int main(void) {h100_bad_pipe();_Exit(0);}')
 c_file.write_text(target);subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and 'EXPECTED_NATIVE_HP_PIPE' in bad.stderr,(bad.returncode,bad.stderr[-1000:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_HTT_CALLBACKS_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_HTT_function_sha256']={n:hashlib.sha256(native(root,n).encode()).hexdigest() for n in NAMES};r['native_HIF_registration_variant_sha256']={k:hashlib.sha256(v.encode()).hexdigest() for k,v in zip(['WDI_enabled','WDI_disabled'],hif_variants(root))};r['native_HTT_entry_prefix_sha256']=hashlib.sha256(entry_prefix(root).encode()).hexdigest();r['source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [HTT,INTERNAL,API,SERVICES,FW_HTC,HTT_HEADER,PACKET]}
 r['additional_composite_cases']=192;r['callback_contract_cases']=64;r['inherited_parser_contract_cases']=303;r['negative_controls_rejected']=82
 r['checks']=['original HTT constructor, HTC attach, send-full handler, HIF HP packet adapter and both original WDI registration variants execute with modeled lower connect/store endpoints','captured native registration callback/context pairs carry ordinary HTC or HIF HP messages through the original consumed-entry prefix into the production parser and native DP peer/VDEV release chain','192 composite selections and 64 constructor/registration/delivery contracts cover WDI on/off, v1/v2, aligned/unaligned buffers, response endpoint, transport failure/cancel, null packet/context/buffer and failed connect','68 inherited controls retain the preceding direct-parser path; 13 new mutations and one unmodified native wrong-pipe rejection pass']
 r['limitations']='Fixture-injected HTC/HIF deliveries, not real service, DMA/bus/interrupt or firmware events. Original generic dispatcher prefix executes only until the production unmap consumer returns; unconsumed generic tail is an abort stub, with narrow unused-local warnings suppressed only around this extracted prefix. WDI-enabled and disabled source variants are tested explicitly, not a claim of phone feature selection. Lower HTC connect, endpoint save, logging init, HIF store, handles and layouts remain models; no real attach-time reentrancy, teardown, deregistration or late-producer race validation. Prior DP construction/reference/peer-gone/platform and cleanup endpoints remain models. Original TX completion is an abort endpoint; send-full KEEP only is exercised. No backend activation, automatic parent shutdown, active SSR, phone/RF or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
