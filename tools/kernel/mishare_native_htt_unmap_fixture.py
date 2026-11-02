#!/usr/bin/env python3
"""Actions-only production HTT unmap parser/ownership into native DP release."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_dp_unmap_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
HTT='qca-wifi-host-cmn/dp/wifi3.0/dp_htt.c'
WIRE='fw-api/fw/htt.h'
PARSER='dp_htt_t2h_peer_unmap_try_handle'
PATCH=Path(__file__).resolve().parents[2]/'kernel/patches/popsicle/0037-htt-peer-unmap-length-and-ownership.patch'
def deswizzle(text):
 return re.search(r'static u_int8_t \*\s*htt_t2h_mac_addr_deswizzle\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)[0]
def wire_definitions(text):
 defs={m[1]:m[0] for m in re.finditer(r'^#define (HTT_\w+)(?:[^\n]*\\\n)*[^\n]*(?:\n|$)',text,re.M)}
 needed=set(['HTT_T2H_MSG_TYPE_GET','HTT_RX_PEER_UNMAP_BYTES','HTT_RX_PEER_UNMAP_V2_BYTES','HTT_RX_PEER_UNMAP_V2_PEER_WDS_FREE_COUNT_OFFSET','HTT_RX_PEER_UNMAP_PEER_ID_GET','HTT_RX_PEER_UNMAP_VDEV_ID_GET','HTT_RX_PEER_UNMAP_V2_SW_PEER_ID_GET','HTT_RX_PEER_UNMAP_V2_VDEV_ID_GET','HTT_RX_PEER_UNMAP_V2_NEXT_HOP_GET','HTT_RX_PEER_UNMAP_V2_PEER_WDS_FREE_COUNT_GET'])
 pending=list(needed)
 while pending:
  name=pending.pop();assert name in defs,name
  for dep in re.findall(r'\bHTT_\w+\b',defs[name]):
   if dep!=name and dep in defs and dep not in needed:needed.add(dep);pending.append(dep)
 return '\n'.join(defs[n].rstrip() for n in sorted(needed))
SUPPORT=r'''
#include <limits.h>
WIRE_ENUM
WIRE_DEFINES
#define DP_PEER_WDS_COUNT_INVALID UINT_MAX
#define QDF_STATUS_E_CANCELED 7
struct h99_nbuf {uint8_t *allocation,*data;unsigned len;bool live;};
typedef struct h99_nbuf *qdf_nbuf_t;
typedef struct {void *pPktContext;QDF_STATUS Status;} HTC_PACKET;
typedef uint8_t u_int8_t;
typedef uint16_t u_int16_t;
typedef uint32_t u_int32_t;
struct htt_soc {struct dp_soc *dp_soc;void *htt_logger_handle;struct {unsigned htc_err_cnt;} stats;};
static struct htt_soc h99_soc;
static struct h99_nbuf *h99_current;
static unsigned h99_calls,h99_frees,h99_logs,h99_expected_count,h99_expected_calls;
static uint16_t h99_expected_peer;
static uint8_t h99_expected_vdev,h99_expected_wds,h99_expected_mac[6];
static bool h99_v2,h99_big,h99_unaligned,h99_probe;
static unsigned h99_length=0;
static size_t h99_len(qdf_nbuf_t b) {assert(b && b->live);return b->len;}
static void *h99_data(qdf_nbuf_t b) {assert(b && b->live);return b->data;}
static void h99_error(const char *fmt,...) __attribute__((format(printf,1,2)));
static void h99_error(const char *fmt,...) {(void)fmt;}
static void h99_copy(void *dest,const void *src,size_t n) {
 assert(h99_current && h99_current->live && src==h99_current->data && n<=h99_current->len && "EXPECTED_HTT_LENGTH_BEFORE_COPY");memcpy(dest,src,n);
}
static void h99_free(qdf_nbuf_t b) {
 assert(b==h99_current && b->live && !h99_frees && "EXPECTED_HTT_EXACTLY_ONE_NBUF_FREE");
 assert(h99_calls==h99_expected_calls && "EXPECTED_HTT_CALLBACK_BEFORE_NBUF_FREE");
 b->live=false;free(b->allocation);b->allocation=b->data=NULL;h99_frees++;
}
static void h99_event(void *logger,unsigned type,uint8_t *data) {
 assert(logger==&h99_soc && (type==HTT_T2H_MSG_TYPE_PEER_UNMAP || type==HTT_T2H_MSG_TYPE_PEER_UNMAP_V2) && data==h99_current->data && h99_current->live && !h99_logs);h99_logs++;
}
static void h99_decoded(struct dp_soc *s,uint16_t id,uint8_t vdev,uint8_t *mac,uint8_t wds,uint32_t count) {
 assert(s==&d96_soc && h99_current->live && h99_logs==1 && !h99_calls && "EXPECTED_HTT_CALLBACK_WHILE_NBUF_LIVE");
 assert(id==h99_expected_peer && vdev==h99_expected_vdev && wds==h99_expected_wds && count==h99_expected_count && !memcmp(mac,h99_expected_mac,6) && "EXPECTED_HTT_GOLDEN_FIELDS");h99_calls++;
 if(!h99_probe){dp_rx_peer_unmap_handler(s,id,vdev,mac,wds,count);}
}
#pragma push_macro("BIG_ENDIAN_HOST")
#undef BIG_ENDIAN_HOST
#define htt_t2h_mac_addr_deswizzle h99_deswizzle_le
NATIVE_DESWIZZLE
#undef htt_t2h_mac_addr_deswizzle
#define BIG_ENDIAN_HOST
#define htt_t2h_mac_addr_deswizzle h99_deswizzle_be
NATIVE_DESWIZZLE
#undef htt_t2h_mac_addr_deswizzle
#undef BIG_ENDIAN_HOST
#pragma pop_macro("BIG_ENDIAN_HOST")
static uint8_t *h99_deswizzle(uint8_t *src,uint8_t *dest) {
 if(h99_big){uint8_t host_bytes[8];for(unsigned word=0;word<2;word++){for(unsigned byte=0;byte<4;byte++){host_bytes[word*4+byte]=src[word*4+3-byte];}}return h99_deswizzle_be(host_bytes,dest);}
 return h99_deswizzle_le(src,dest);
}
PARSER_MACROS
PRODUCTION_PARSER
PARSER_UNMACROS
static void h99_build(struct h99_nbuf *b,unsigned type,uint16_t id,uint8_t vdev,uint8_t wds,uint32_t count,const uint8_t *mac,unsigned len,unsigned offset) {
 uint32_t words[9]={0};uint8_t payload[8]={0};
 /* Independent encoder: literal wire positions, not parser GET macros. */
 words[0]=(uint32_t)type|((uint32_t)vdev<<8)|((uint32_t)id<<16);
 if(type==0x1f){memcpy(payload,mac,6);memcpy(words+1,payload,8);words[2]|=(uint32_t)wds<<16;words[4]=count;}
 assert(len<=sizeof(words));b->allocation=malloc((len+offset)?len+offset:1);assert(b->allocation);b->data=b->allocation+offset;b->len=len;b->live=true;memcpy(b->data,words,len);
 h99_current=b;h99_calls=h99_frees=h99_logs=0;h99_expected_peer=id;h99_expected_vdev=vdev;h99_expected_wds=(type==0x1f)?wds:0;h99_expected_count=(type==0x1f)?count:UINT_MAX;
 memset(h99_expected_mac,0,6);if(type==0x1f){memcpy(h99_expected_mac,mac,6);}
 h99_soc.dp_soc=&d96_soc;h99_soc.htt_logger_handle=&h99_soc;
}
static void h99_unmap(struct dp_soc *s,uint16_t id,uint8_t vdev,uint8_t *mac,uint8_t wds,uint32_t count) {
 if(!h99_enabled){dp_rx_peer_unmap_handler(s,id,vdev,mac,wds,count);return;}
 struct h99_nbuf b;bool v2=h99_v2 || wds;unsigned len=h99_length?h99_length:(v2?20:4);
 /* All preflight WDS probes need v2 fields even when main case selects v1. */
 if(wds && len<20){len=20;}
 uint8_t golden[6]={0x12,0x34,0x56,0x78,0x9a,0xbc};h99_build(&b,v2?0x1f:0x04,id,vdev,wds,count,golden,len,h99_unaligned);
 h99_expected_calls=1;HTC_PACKET pkt={.pPktContext=&b,.Status=QDF_STATUS_SUCCESS};
 assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt) && !b.live && h99_calls==1 && h99_frees==1 && h99_logs==1 && "EXPECTED_HTT_PARSED_DELIVERY_AND_FREE");
}
static void h99_contract_one(unsigned type,unsigned len,unsigned offset,QDF_STATUS status) {
 struct h99_nbuf b;uint8_t mac[6]={0x12,0x34,0x56,0x78,0x9a,0xbc};h99_build(&b,type,42,7,1,0x1234,mac,len,offset);
 bool header=len>=4;bool recognized=type==0x04 || type==0x1f;bool valid=status==QDF_STATUS_SUCCESS && header && recognized && (type==0x04 || len>=20);
 h99_expected_calls=valid;unsigned errors=h99_soc.stats.htc_err_cnt;HTC_PACKET pkt={.pPktContext=&b,.Status=status};bool consumed=dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt);
 assert(consumed==(status!=QDF_STATUS_SUCCESS || !header || recognized) && "EXPECTED_HTT_UNKNOWN_TYPE_BORROWED");
 assert(h99_calls==(unsigned)valid && h99_logs==(unsigned)valid && "EXPECTED_HTT_LENGTH_OR_STATUS_ADMISSION");
 assert(h99_soc.stats.htc_err_cnt==errors+(unsigned)(status!=QDF_STATUS_SUCCESS && status!=QDF_STATUS_E_CANCELED) && "EXPECTED_HTT_CANCEL_NOT_TRANSPORT_ERROR");
 if(!consumed){assert(b.live && !h99_frees && "EXPECTED_HTT_UNHANDLED_CALLER_OWNERSHIP");h99_free(&b);}
 assert(!b.live && h99_frees==1 && "EXPECTED_HTT_EXACTLY_ONE_NBUF_FREE");
}
static void h99_contracts(void) {
 h99_probe=true;unsigned count=0;
 for(unsigned big=0;big<2;big++){h99_big=big;for(unsigned offset=0;offset<2;offset++){for(unsigned fmt=0;fmt<2;fmt++){for(unsigned len=0;len<=36;len++){h99_contract_one(fmt?0x1f:0x04,len,offset,QDF_STATUS_SUCCESS);count++;}}}}
 assert(count==296);
 h99_contract_one(0x40,4,0,QDF_STATUS_SUCCESS);count++;
 h99_contract_one(0x04,0,0,QDF_STATUS_E_FAILURE);count++;
 h99_contract_one(0x1f,1,1,QDF_STATUS_E_CANCELED);count++;
 struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,0x1f,42,7,0,0,mac,20,0);h99_expected_calls=0;HTC_PACKET pkt={.pPktContext=&b,.Status=QDF_STATUS_SUCCESS};b.data=NULL;
 assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt) && !b.live && h99_frees==1);count++;
 h99_build(&b,0x04,42,7,0,0,mac,4,0);h99_expected_calls=0;pkt.pPktContext=&b;assert(dp_htt_t2h_peer_unmap_try_handle(NULL,&pkt) && !b.live && h99_frees==1);count++;
 pkt.pPktContext=NULL;assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,&pkt));count++;
 assert(dp_htt_t2h_peer_unmap_try_handle(&h99_soc,NULL));count++;assert(count==303);
 h99_probe=h99_big=false;
}
'''
MACROS={'QDF_MAC_ADDR_SIZE':'6','qdf_nbuf_len':'h99_len','qdf_nbuf_data':'h99_data','qdf_mem_copy':'h99_copy','dp_htt_rx_nbuf_free':'h99_free','dp_htt_err':'h99_error','htt_event_record':'h99_event','htt_t2h_mac_addr_deswizzle':'h99_deswizzle','dp_rx_peer_unmap_handler':'h99_decoded'}
def source_contract(root):
 text=(root/HTT).read_text();handler=extract(text,'dp_htt_t2h_msg_handler');assert handler.index('dp_htt_t2h_peer_unmap_try_handle(context, pkt)')<handler.index('pkt->pPktContext');assert 'case HTT_T2H_MSG_TYPE_PEER_UNMAP:' not in handler and 'case HTT_T2H_MSG_TYPE_PEER_UNMAP_V2:' not in handler
 assert 'connect.EpCallbacks.EpRecv = dp_htt_t2h_msg_handler;' in text
 return handler

def fixture(root):
 s,exits,stubbed=previous.fixture(root);source_contract(root);text=(root/HTT).read_text();wire=(root/WIRE).read_text();start,end=previous.macros(MACROS)
 enum=re.search(r'enum htt_t2h_msg_type \{.*?^\};',wire,re.S|re.M)[0]
 block=SUPPORT.replace('\nWIRE_ENUM\n','\n'+enum+'\n').replace('\nWIRE_DEFINES\n','\n'+wire_definitions(wire)+'\n').replace('\nNATIVE_DESWIZZLE\n','\n'+deswizzle(text)+'\n').replace('\nPARSER_MACROS\n','\n'+start+'\n').replace('\nPRODUCTION_PARSER\n','\n'+extract(text,PARSER)+'\n').replace('\nPARSER_UNMACROS\n','\n'+end+'\n')
 anchor='static void d98_finish(void);';s=owner.replace_once(s,anchor,'static bool h99_enabled;\nstatic unsigned h99_expected_count;\nstatic void h99_unmap(struct dp_soc *,uint16_t,uint8_t,uint8_t *,uint8_t,uint32_t);\n'+anchor)
 s=owner.replace_once(s,'count==0 && !d98_step','count==(h99_enabled?h99_expected_count:0) && !d98_step')
 for name in ['d98_preflight','d98_finish']:
  body=function(s,name);s=owner.replace_once(s,body,body.replace('dp_rx_peer_unmap_handler(','h99_unmap('))
 check=function(s,'d98_finish');s=owner.replace_once(s,check,check+'\n'+block)
 case=function(s,'p92_case');s=owner.replace_once(s,case,owner.replace_once(case,'d98_enabled=true;','h99_enabled=true;d98_enabled=true;'))
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++){for(unsigned v2=0;v2<2;v2++){for(unsigned unaligned=0;unaligned<2;unaligned++){for(unsigned big=0;big<2;big++){
  pid_t c=fork();assert(c>=0);if(!c){h99_v2=v2;h99_unaligned=unaligned;h99_big=big;h99_length=v2?28:8;d98_probes=true;d98_txrx=true;d98_ol=true;d98_partner_enabled=true;d97_extra=2;d97_rx=true;d97_reverse=trace;d96_extra=2;d96_notify_enabled=true;p92_case(trace,1,0,false);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }}}}
 assert(count==168);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==152);','assert(count==152);\n'+extra))
 main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'p94_map_contract();','h99_contracts();p94_map_contract();'))
 assert s.count(extract(text,PARSER))==1 and s.count(deswizzle(text))==2
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 old=owner.replace_once(source,'h99_enabled=true;','h99_enabled=false;');previous.negative_controls(directory,c_file,command,env,old,root);exe=directory/'engine';body=extract((root/HTT).read_text(),PARSER)
 controls=[
 ('header','qdf_nbuf_len(msg) < sizeof(words[0])','(false && qdf_nbuf_len(msg) < sizeof(words[0]))','h99_contract_one(0x04,3,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_LENGTH_BEFORE_COPY'),
 ('v2_length','if (qdf_nbuf_len(msg) < required)','if (false && qdf_nbuf_len(msg) < required)','h99_contract_one(0x1f,19,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_LENGTH_BEFORE_COPY'),
 ('v1_id','peer_id = HTT_RX_PEER_UNMAP_PEER_ID_GET(words[0]);','peer_id = 43;','h99_contract_one(0x04,4,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('v2_id','peer_id = HTT_RX_PEER_UNMAP_V2_SW_PEER_ID_GET(words[0]);','peer_id = 43;','h99_contract_one(0x1f,20,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('vdev','vdev_id = HTT_RX_PEER_UNMAP_V2_VDEV_ID_GET(words[0]);','vdev_id = 8;','h99_contract_one(0x1f,20,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('wds','is_wds = HTT_RX_PEER_UNMAP_V2_NEXT_HOP_GET(words[2]);','is_wds = 0;','h99_contract_one(0x1f,20,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('count','HTT_RX_PEER_UNMAP_V2_PEER_WDS_FREE_COUNT_GET(words[4]);','0;','h99_contract_one(0x1f,20,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('mac','mac = htt_t2h_mac_addr_deswizzle((u_int8_t *)(words + 1),\n\t\t\t\t\t       mac_buffer);','mac = (u_int8_t *)(words + 2);','h99_big=true;h99_contract_one(0x1f,20,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_GOLDEN_FIELDS'),
 ('free','dp_htt_rx_nbuf_free(msg);\n\treturn true;\n}','/* omit final buffer free */\n\treturn true;\n}','h99_contract_one(0x04,4,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_EXACTLY_ONE_NBUF_FREE'),
 ('callback','dp_rx_peer_unmap_handler(soc->dp_soc, peer_id, vdev_id, mac,\n\t\t\t\t is_wds, free_wds_count);','(void)peer_id;(void)vdev_id;(void)mac;(void)is_wds;(void)free_wds_count;','h99_contract_one(0x04,4,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_CALLBACK_BEFORE_NBUF_FREE'),
 ('cancel','if (pkt->Status != QDF_STATUS_E_CANCELED)','if (true)','h99_contract_one(0x04,0,0,QDF_STATUS_E_CANCELED);','EXPECTED_HTT_CANCEL_NOT_TRANSPORT_ERROR'),
 ('unknown','return false;','return true;','h99_contract_one(0x40,4,0,QDF_STATUS_SUCCESS);','EXPECTED_HTT_UNKNOWN_TYPE_BORROWED'),
 ]
 for label,needle,mutation,call,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {h99_probe=true;'+call+'_Exit(0);}')
  c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_HTT_UNMAP_COMPOSITE_FIXTURE_PASS_ONLY'
 r['production_HTT_parser_sha256']=hashlib.sha256(extract((root/HTT).read_text(),PARSER).encode()).hexdigest();r['patched_HTT_source_sha256']=hashlib.sha256((root/HTT).read_bytes()).hexdigest();r['HTT_dispatcher_sha256']=hashlib.sha256(source_contract(root).encode()).hexdigest();r['native_deswizzle_sha256']=hashlib.sha256(deswizzle((root/HTT).read_text()).encode()).hexdigest();r['wire_header_sha256']=hashlib.sha256((root/WIRE).read_bytes()).hexdigest();r['wire_definition_subset_sha256']=hashlib.sha256(wire_definitions((root/WIRE).read_text()).encode()).hexdigest();r['production_patch_sha256']=hashlib.sha256(PATCH.read_bytes()).hexdigest()
 r['additional_composite_cases']=168;r['parser_contract_cases']=303;r['negative_controls_rejected']=68
 r['checks']=['production patch installs a length-checked HTT unmap consumer before generic packet-context/header reads, preserving non-unmap caller ownership and unselected switch arms','production helper and original deswizzle execute with original wire enum/GET macros; independent encoder tests v1 four-byte and v2 twenty-byte consumed prefixes, optional trailing bytes, unaligned data and both deswizzle source branches','168 composite selections deliver through production parser into native lookup/map removal/unmap/peer and VDEV finalizers; 303 parser contracts include all lengths 0..36, transport failure/cancel, borrowed unknown type, null packet/context/data/buffer','56 inherited controls retain old unmap route; 12 parser mutations rejected; checked trampoline forwards production runtime completion after actual host DP storage frees']
 r['limitations']='Production parser helper executes from modeled HTC packet/nbuf delivery; full generic dispatcher and actual HTC/HIF service registration/firmware transport are source-reviewed/compiled, not executed in host fixture. Nbuf storage is host heap, atomics/locks/maps, initial reference graph and DP cleanup/event/AST/flow/statistics endpoints remain models. BIG_ENDIAN_HOST probe executes its source branch on a little-endian host with modeled host-word MAC swizzling, not a real big-endian platform. No general validation of other HTT message formats, no firmware delivery/concurrency, production parent shutdown coordinator, active SSR, phone/RF or AirDrop certification. Backend remains disabled.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
