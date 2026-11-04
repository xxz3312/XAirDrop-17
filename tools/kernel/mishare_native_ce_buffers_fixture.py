#!/usr/bin/env python3
"""Actions-only native residual CE RX/TX cleanup and ownership."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import mishare_native_ce_stop_fixture as previous
owner=previous.owner
engine=previous.engine
function=previous.function
native=previous.native
CE=previous.CE
API='qca-wifi-host-cmn/hif/src/ce/ce_api.h'
NAMES=['hif_recv_buffer_cleanup_on_pipe','hif_send_buffer_cleanup_on_pipe']
SUPPORT=r'''
typedef uint64_t qdf_dma_addr_t;
/* DMA direction is a model token, checked at the primitive boundary. */
#define QDF_DMA_FROM_DEVICE 103
NATIVE_SENTINEL
static unsigned h103_rxmode,h103_txmode,h103_rpos,h103_tpos,h103_pages,h103_unmaps,h103_rx_frees,h103_tx_calls;
static bool h103_offset,h103_unmapped[5];
static struct h99_nbuf h103_buffers[5];
static struct HIF_CE_pipe_info *h103_pipe;
static void h103_allocate(void) {for(unsigned i=0;i<5;i++){struct h99_nbuf *b=&h103_buffers[i];b->allocation=malloc(17);assert(b->allocation);b->data=b->allocation+h103_offset;b->len=16;b->live=true;}}
static int h103_index(qdf_nbuf_t b) {for(unsigned i=0;i<5;i++){if(b==&h103_buffers[i])return i;}assert(!"EXPECTED_OWNED_RESIDUAL_BUFFER");return -1;}
static void h103_payload_free(qdf_nbuf_t b) {assert(b->live && "EXPECTED_RESIDUAL_EXACTLY_ONCE_FREE");b->live=false;free(b->allocation);b->allocation=b->data=NULL;}
static QDF_STATUS h103_direct(struct HIF_CE_state *s,unsigned pipe) {assert(s==&h101_hif.ce);if(pipe!=2)return QDF_STATUS_E_FAILURE;h103_pages++;return h103_rxmode==4?QDF_STATUS_SUCCESS:QDF_STATUS_E_FAILURE;}
static QDF_STATUS h103_revoke(struct CE_handle *h,void **context,void **buffer,qdf_dma_addr_t *dma) {
 if(h!=&h102_handles[2])return QDF_STATUS_E_FAILURE;
 assert(h103_pages==1 && h103_rxmode!=4 && "EXPECTED_DIRECT_LINK_OWNERSHIP_GATE");
 if(h103_rxmode==5 || h103_rpos==3)return QDF_STATUS_E_FAILURE;
 unsigned i=h103_rpos++;*context=h103_pipe;*dma=0x1030+i;*buffer=i==1?NULL:&h103_buffers[i==0?0:1];return QDF_STATUS_SUCCESS;
}
static void h103_unmap(void *dev,qdf_nbuf_t b,unsigned direction) {int i=h103_index(b);assert(dev==&h102_device && direction==QDF_DMA_FROM_DEVICE && i<2 && b->live && !h103_unmapped[i] && "EXPECTED_RX_UNMAP_ONCE");h103_unmapped[i]=true;h103_unmaps++;}
static void h103_rx_free(qdf_nbuf_t b) {int i=h103_index(b);assert(i<2 && h103_unmapped[i] && "EXPECTED_RX_UNMAP_BEFORE_FREE");h103_payload_free(b);h103_rx_frees++;}
static QDF_STATUS h103_cancel(struct CE_handle *h,void **context,void **buffer,qdf_dma_addr_t *dma,unsigned *bytes,unsigned *id,unsigned *hash) {
 if(h!=&h102_handles[2])return QDF_STATUS_E_FAILURE;
 unsigned total=h103_txmode==1?4:3;if(h103_txmode==5 || h103_tpos==total)return QDF_STATUS_E_FAILURE;
 unsigned i=h103_tpos++;*context=h103_pipe;*dma=0x2030+i;*bytes=16;*id=(h103_txmode==1 && i==2)?6:7;*hash=0xabc0+i;
 *buffer=i==0?CE_SENDLIST_ITEM_CTXT:&h103_buffers[i==1?2:(h103_txmode==1 && i==2)?3:4];return QDF_STATUS_SUCCESS;
}
static void h103_tx_complete(void *context,qdf_nbuf_t b,unsigned id,unsigned hash) {assert(context==h103_pipe && b!=CE_SENDLIST_ITEM_CTXT && "EXPECTED_NO_SENDLIST_COMPLETION");assert(id==7 && "EXPECTED_NO_HTT_DOUBLE_COMPLETION");int i=h103_index(b);assert((i==2 || i==4) && hash==0xabc0+(i==2?1u:2u));h103_payload_free(b);h103_tx_calls++;}
NATIVE_RX
NATIVE_TX
static void h103_setup(void) {
 h103_pipe=&h101_hif.ce.pipe_info[2];h103_pipe->pipe_num=2;h101_hif.htc_htt_tx_endpoint=6;
 for(unsigned i=0;i<16;i++){h101_hif.ce.pipe_info[i].HIF_CE_state=&h101_hif.ce;}
 h103_pipe->pipe_callbacks.Context=h103_pipe;h103_pipe->pipe_callbacks.txCompletionHandler=h103_txmode==2?NULL:h103_tx_complete;h103_allocate();
}
static void h103_check(void) {
 bool rx=h103_rxmode==0,tx=h103_txmode<2;
 assert(h103_unmaps==(rx?2u:0u) && h103_rx_frees==(rx?2u:0u) && h103_pages==(h103_rxmode==0 || h103_rxmode==4 || h103_rxmode==5?1u:0u) && "EXPECTED_RX_CLEANUP_GATES");
 assert(h103_tx_calls==(tx?(h103_txmode==1?1u:2u):0u) && h103_tpos==(h103_txmode==3 || h103_txmode==4 || h103_txmode==5?0u:3u) && "EXPECTED_TX_CLEANUP_OWNERSHIP");
 assert(h103_buffers[3].live && "EXPECTED_HTT_BUFFER_REMAINS_OTHER_OWNER");
 for(unsigned i=0;i<5;i++){bool freed=i<2?rx:(i==2?tx:i==4?(tx && h103_txmode==0):false);assert(h103_buffers[i].live==!freed && "EXPECTED_RESIDUAL_OWNER_LEDGER");if(h103_buffers[i].live){h103_payload_free(&h103_buffers[i]);}}
}
static void h103_case(unsigned rx,unsigned tx,bool offset) {
 h103_rxmode=rx;h103_txmode=tx;h103_offset=offset;h101_hif.qdf_dev=&h102_device;h101_hif.ce.started=true;h103_setup();h103_pipe->ce_hdl=&h102_handles[2];h103_pipe->buf_sz=36;
 if(rx==1){h103_pipe->buf_sz=0;}if(rx==2){h101_hif.ce.started=false;}if(rx==3){h101_hif.qdf_dev=NULL;}
 h103_native_rx(h103_pipe);
 h103_pipe->buf_sz=tx==3?0:36;h101_hif.ce.started=tx!=4;
 h103_native_tx(h103_pipe);h103_check();
}
static void h103_integrated(unsigned flags) {h103_enabled=true;h103_rxmode=flags&1?4:0;h103_txmode=flags&2?1:0;h103_offset=!!(flags&4);h102_case(8|(flags&4?2:0)|(flags&8?128:0));h103_check();}
static void h103_contracts(void) {
 unsigned count=0;
 for(unsigned rx=0;rx<6;rx++){for(unsigned tx=0;tx<6;tx++){for(unsigned off=0;off<2;off++){pid_t c=fork();assert(c>=0);if(!c){h103_case(rx,tx,off);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;}}}
 for(unsigned flags=0;flags<16;flags++){pid_t c=fork();assert(c>=0);if(!c){h103_integrated(flags);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;}assert(count==88);
}
'''
def fixture(root):
 s,exits,stubbed=previous.fixture(root)
 s=owner.replace_once(s,'void *txCompletionHandler;','void (*txCompletionHandler)(void *,qdf_nbuf_t,unsigned,unsigned);')
 s=owner.replace_once(s,'struct HIF_CE_pipe_info {','struct HIF_CE_pipe_info {struct HIF_CE_state *HIF_CE_state;')
 s=owner.replace_once(s,'struct hif_softc {','struct hif_softc {unsigned htc_htt_tx_endpoint;')
 s=owner.replace_once(s,'static bool h102_enabled;','static bool h102_enabled;\nstatic bool h103_enabled;\nstatic void h103_setup(void);\nstatic void h103_native_rx(struct HIF_CE_pipe_info *);\nstatic void h103_native_tx(struct HIF_CE_pipe_info *);')
 for name,call in [('h102_recv_cleanup','h103_native_rx'),('h102_send_cleanup','h103_native_tx')]:
  body=function(s,name);needle='h102_recv_count[i]++;' if name=='h102_recv_cleanup' else 'h102_send_count[i]++;';s=owner.replace_once(s,body,owner.replace_once(body,needle,needle+'if(h103_enabled){'+call+'(p);}'))
 body=function(s,'h102_prepare');s=owner.replace_once(s,body,owner.replace_once(body,'assert(!pthread_create','if(h103_enabled){h103_setup();}\n assert(!pthread_create'))
 block=SUPPORT.replace('\nNATIVE_SENTINEL\n','\n'+previous.previous.previous.define((root/API).read_text(),'CE_SENDLIST_ITEM_CTXT')+'\n')
 maps=[{'hif_recv_buffer_cleanup_on_pipe':'h103_native_rx','HIF_GET_SOFTC':'h101_softc','hif_free_pages_for_direct_link_recv_pipe':'h103_direct','ce_revoke_recv_next':'h103_revoke','qdf_nbuf_unmap_single':'h103_unmap','hif_ce_rx_nbuf_free':'h103_rx_free'}, {'hif_send_buffer_cleanup_on_pipe':'h103_native_tx','HIF_GET_SOFTC':'h101_softc','ce_cancel_send_next':'h103_cancel'}]
 for token,name,mapping in zip(['NATIVE_RX','NATIVE_TX'],NAMES,maps):block=block.replace('\n'+token+'\n','\n'+previous.previous.scoped(native(root,CE,name),mapping)+'\n')
 anchor=function(s,'h102_contracts');s=owner.replace_once(s,anchor,anchor+'\n'+block);main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'h102_contracts();','h102_contracts();h103_contracts();'))
 return s,exits,stubbed
def negative_controls(directory,c_file,command,env,source,root):
 old,*_=previous.fixture(root);previous.negative_controls(directory,c_file,command,env,old,root);exe=directory/'engine'
 controls=[(NAMES[0],'if (buf_sz == 0)','if (false && buf_sz == 0)','h103_case(1,0,false);','EXPECTED_RX_CLEANUP_GATES'),(NAMES[0],'if (!hif_state->started)','if (false && !hif_state->started)','h103_case(2,0,false);','EXPECTED_RX_CLEANUP_GATES'),(NAMES[0],'if (QDF_IS_STATUS_SUCCESS(status))','if (false && QDF_IS_STATUS_SUCCESS(status))','h103_case(4,0,false);','EXPECTED_DIRECT_LINK_OWNERSHIP_GATE'),(NAMES[0],'qdf_nbuf_unmap_single(scn->qdf_dev, netbuf,\n\t\t\t\t\t      QDF_DMA_FROM_DEVICE);','/* omit unmap */','h103_case(0,0,false);','EXPECTED_RX_UNMAP_BEFORE_FREE'),(NAMES[1],'if (netbuf != CE_SENDLIST_ITEM_CTXT)','if (true)','h103_case(0,0,false);','EXPECTED_NO_SENDLIST_COMPLETION'),(NAMES[1],'if (id == scn->htc_htt_tx_endpoint)','if (false && id == scn->htc_htt_tx_endpoint)','h103_case(0,1,false);','EXPECTED_NO_HTT_DOUBLE_COMPLETION')]
 for name,needle,mutation,call,marker in controls:
  body=native(root,CE,name);target=owner.replace_once(source,function(source,'main'),'int main(void) {'+call+'_Exit(0);}')
  c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(name,bad.returncode,bad.stderr[-1000:])
def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_CE_BUFFERS_FIXTURE_PASS_ONLY';r['native_function_sha256']={n:hashlib.sha256(native(root,CE,n).encode()).hexdigest() for n in NAMES};r['source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [CE,API]};r['residual_buffer_contract_cases']=88;r['negative_controls_rejected']=116;r['checks']=['72 standalone RX/TX gate and ownership selections plus 16 native CE-stop integrations after controlled producer join','Original RX unmap-before-free, direct-link ownership, NULL revoked descriptors, TX sendlist sentinel, HTT early return and optional completion callback executed'];r['limitations']='CE revoke/cancel rings, DMA unmap, direct-link ownership and TX completion remain models. Payload malloc/free is host-only. HTT-owned and no-callback payloads remain owned until explicit model-owner cleanup. Native send-complete, real rings/DMA, physical HTT free, production shutdown coordination, phone/RF and AirDrop are not certified. Backend remains disabled.';return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
