// SPDX-License-Identifier: GPL-2.0-only
#define ACTION_TX_TEST
#include "../native/wireless/action_tx.c"
#include <assert.h>

/* A kernel NLMSG_ERROR timeout and a receive timeout share errno 110.
 * Preserve matching-sequence error provenance; ACK/unrelated errors do not. */
static void request_error_tests(void) {
    struct client c={.seq=77,.family=25};
    struct message m={.n=NLMSG_LENGTH(sizeof(struct nlmsgerr))};
    struct nlmsghdr h={.nlmsg_len=(uint32_t)m.n,.nlmsg_type=NLMSG_ERROR,.nlmsg_seq=77};
    struct nlmsgerr e={.error=-ETIMEDOUT};struct bytes reply;
    memcpy(m.data,&h,sizeof(h));memcpy(m.data+NLMSG_HDRLEN,&e,sizeof(e));
    c.request_error_stage="reply_parse";
    assert(consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply)==-ETIMEDOUT);
    assert(!strcmp(c.request_error_stage,"kernel_reply"));
    h.nlmsg_seq=78;memcpy(m.data,&h,sizeof(h));c.request_error_stage="reply_parse";
    assert(!consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply));
    assert(!strcmp(c.request_error_stage,"reply_parse"));
    h.nlmsg_seq=77;e.error=0;memcpy(m.data,&h,sizeof(h));memcpy(m.data+NLMSG_HDRLEN,&e,sizeof(e));
    assert(!consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply));
    assert(!strcmp(c.request_error_stage,"reply_parse"));
    e.error=ETIMEDOUT;memcpy(m.data+NLMSG_HDRLEN,&e,sizeof(e));
    assert(consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply)==-EBADMSG);
    assert(!strcmp(c.request_error_stage,"reply_parse"));
    assert(consume(&c,m.data,m.n-1,NL80211_CMD_VENDOR,&reply)==-EBADMSG);
}

static unsigned char mac[6]={2,1,2,3,4,5};
struct radio_model {
    struct channel_interface tx,mon;
    unsigned queries,sets,last_freq;
    int set_error,query_error;
    bool roam_after_set,roamed;
};
static int model_query(void *context,unsigned index,struct channel_interface *out) {
    struct radio_model *r=context;r->queries++;
    if (r->query_error) return r->query_error;
    *out=index==r->tx.index?r->tx:r->mon;
    if (r->roamed && index==r->tx.index) out->freq=5200;
    return 0;
}
static int model_set(void *context,unsigned index,unsigned freq) {
    struct radio_model *r=context;assert(index==r->mon.index);
    r->sets++;r->last_freq=freq;
    if (!r->set_error && r->roam_after_set) r->roamed=true;
    return r->set_error;
}
static void channel_tests(void) {
    struct radio_model r={.tx={4,2,NL80211_IFTYPE_STATION,5180},.mon={6,2,NL80211_IFTYPE_MONITOR,0}};
    struct channel_follow f={.tx=4,.monitor=6};
    assert(follow_channel(&f,&r,model_query,model_set)==1 && f.freq==5180 && r.sets==1 && !f.changes);
    assert(!follow_channel(&f,&r,model_query,model_set) && r.sets==1);
    r.mon.freq=5200;
    assert(follow_channel(&f,&r,model_query,model_set)==1 && r.sets==2 && r.last_freq==5180);
    r.mon.freq=0;r.sets=1;f.changes=0;
    r.tx.freq=2412;
    assert(follow_channel(&f,&r,model_query,model_set)==1 && f.freq==2412 && f.changes==1 && r.last_freq==2412);
    r.tx.freq=0;assert(follow_channel(&f,&r,model_query,model_set)==-ENOLINK && r.sets==2 && f.freq==2412);
    r.tx.freq=5955;assert(follow_channel(&f,&r,model_query,model_set)==-ENOLINK);
    r.tx.freq=5180;r.mon.phy=3;assert(follow_channel(&f,&r,model_query,model_set)==-EXDEV && r.sets==2);
    r.mon.phy=2;r.mon.type=NL80211_IFTYPE_STATION;assert(follow_channel(&f,&r,model_query,model_set)==-EXDEV);
    r.mon.type=NL80211_IFTYPE_MONITOR;r.tx.type=NL80211_IFTYPE_AP;assert(follow_channel(&f,&r,model_query,model_set)==-EXDEV);
    r.tx.type=NL80211_IFTYPE_P2P_CLIENT;r.set_error=-EBUSY;
    assert(follow_channel(&f,&r,model_query,model_set)==-EBUSY && f.freq==2412 && f.changes==1);
    r.set_error=0;r.roam_after_set=true;
    assert(follow_channel(&f,&r,model_query,model_set)==-EAGAIN && f.freq==2412 && f.changes==1);
    r.roam_after_set=false;r.roamed=false;r.query_error=-ENODEV;unsigned sets=r.sets;
    assert(follow_channel(&f,&r,model_query,model_set)==-ENODEV && r.sets==sets);
    r.query_error=0;r.tx.phy=r.mon.phy=7;
    assert(follow_channel(&f,&r,model_query,model_set)==-EXDEV && r.sets==sets);
    struct message m={0};unsigned index=4,phy=0,type=NL80211_IFTYPE_STATION,freq=5180;
    assert(!add_attr(&m,NL80211_ATTR_IFINDEX,&index,4));assert(!add_attr(&m,NL80211_ATTR_WIPHY,&phy,4));
    assert(!add_attr(&m,NL80211_ATTR_IFTYPE,&type,4));struct channel_interface info;
    assert(!parse_interface((struct bytes){m.data,m.n},4,&info) && !info.freq && info.phy==0);
    assert(parse_interface((struct bytes){m.data,m.n},5,&info)==-EBADMSG);
    assert(!add_attr(&m,NL80211_ATTR_WIPHY_FREQ,&freq,4));
    assert(!parse_interface((struct bytes){m.data,m.n},4,&info) && info.freq==5180);
    assert(!add_attr(&m,NL80211_ATTR_WIPHY_FREQ,&freq,4));
    assert(parse_interface((struct bytes){m.data,m.n},4,&info)==-EBADMSG);
    struct { struct nlmsghdr h;struct nlmsgerr error; } ack={.h={.nlmsg_len=sizeof(ack),.nlmsg_type=NLMSG_ERROR,.nlmsg_seq=9}};
    assert(!channel_ack((void *)&ack,sizeof(ack),8));assert(channel_ack((void *)&ack,sizeof(ack),9)==1);
    ack.error.error=-EPERM;assert(channel_ack((void *)&ack,sizeof(ack),9)==-EPERM);
    ack.error.error=1;assert(channel_ack((void *)&ack,sizeof(ack),9)==-EBADMSG);
    assert(channel_ack((void *)&ack,sizeof(ack)-1,9)==-EBADMSG);
    int sockets[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,sockets));
    assert(send(sockets[0],"old",3,0)==3 && send(sockets[0],"old",3,0)==3);
    unsigned dropped=0;assert(!drain_capture(sockets[1],&dropped) && dropped==2);
    close(sockets[0]);close(sockets[1]);
    puts("CHANNEL_FOLLOW_MODEL_PASS_ONLY");
}
static void action(unsigned char *frame) {
    memset(frame,0,25);frame[0]=0xd0;memset(frame+4,0xff,6);
    memcpy(frame+10,mac,6);memset(frame+16,0xff,6);frame[24]=127;
}
static void vendor_relay_tests(void) {
    unsigned char f[28];bool native=false;
    action(f);f[25]=2;f[26]=0;f[27]=0;
    assert(!prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native) && native);
    f[10]^=1;
    assert(prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native)==-EADDRNOTAVAIL);
    assert(!prepare_feedback_frame(false,false,true,f,sizeof(f),mac,true,&native) && !memcmp(f+10,mac,6));
    f[24]=4;assert(prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native)==-EOPNOTSUPP);
    assert(!prepare_feedback_frame(false,true,false,f,sizeof(f),mac,false,&native) && !native);
    f[24]=127;f[0]=8;
    assert(prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native)==-EOPNOTSUPP);
    f[0]=0xd0;f[1]=0x40;
    assert(prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native)==-EOPNOTSUPP);
    f[1]=0;f[22]=1;
    assert(prepare_feedback_frame(false,false,true,f,sizeof(f),mac,false,&native)==-EOPNOTSUPP);
    assert(native_completion_outcome(0)==WONDER_FB_NOACK);
    assert(native_completion_outcome(1)==WONDER_FB_FAILED);
    assert(relay_feedback_outcome(true,0,native_completion_outcome(0))==WONDER_FB_NOACK);
    assert(relay_feedback_outcome(true,-ETIMEDOUT,WONDER_FB_NOACK)==WONDER_FB_FAILED);
    assert(relay_feedback_outcome(true,0,WONDER_FB_ACKED)==WONDER_FB_FAILED);
    assert(relay_feedback_outcome(false,0,WONDER_FB_ACKED)==WONDER_FB_ACKED);
    /* Actual token completion message carries NOACK=1, preserving owner/token. */
    struct client q={.family=25,.ifindex=7};struct message m;struct bytes payload;
    unsigned outcome=relay_feedback_outcome(true,0,native_completion_outcome(0));
    assert(!feedback_message(&q,&m,WONDER_FB_COMPLETE,11,99,outcome));
    struct bytes attrs={m.data+NLMSG_HDRLEN+GENL_HDRLEN,m.n-NLMSG_HDRLEN-GENL_HDRLEN};
    assert(attr(attrs,NL80211_ATTR_VENDOR_DATA,&payload)==1);
    assert(fb64(payload.p+8)==11 && fb64(payload.p+16)==99 && wonder_fb_word(payload.p+24)==WONDER_FB_NOACK);
}
static void status_message(struct message *m,unsigned index,uint64_t cookie,
                           const unsigned char *frame,size_t len,bool ack) {
    begin(m,25,NL80211_CMD_FRAME_TX_STATUS,0);
    assert(!add_attr(m,NL80211_ATTR_IFINDEX,&index,4));
    assert(!add_attr(m,NL80211_ATTR_COOKIE,&cookie,8));
    assert(!add_attr(m,NL80211_ATTR_FRAME,frame,len));
    if (ack) assert(!add_attr(m,NL80211_ATTR_ACK,NULL,0));
    ((struct nlmsghdr *)(void *)m->data)->nlmsg_len=(uint32_t)m->n;
}
static void awdl_observation_tests(void) {
    unsigned char f[80]={0xd0};f[24]=127;f[26]=0x17;f[27]=0xf2;
    f[28]=8;f[29]=0x10;
    struct awdl_observation o;
    assert(inspect_awdl(f,40,&o)==1 && o.subtype==0 && !o.tlvs);
    f[30]=3;f[40]=4;f[41]=1;f[43]=9;f[44]=18;f[47]=24;
    assert(inspect_awdl(f,50,&o)==1 && o.subtype==3 && o.tlvs==3 && o.sync==1 && o.channels==1 && o.election==1);
    for (size_t n=28;n<40;n++) assert(inspect_awdl(f,n,&o)==-EBADMSG);
    f[41]=255;assert(inspect_awdl(f,50,&o)==-EBADMSG && !o.tlvs);f[41]=1;
    assert(inspect_awdl(f,49,&o)==-EBADMSG);assert(inspect_awdl(f,51,&o)==-EBADMSG);
    f[29]=0x20;assert(inspect_awdl(f,50,&o)==-EPROTONOSUPPORT);f[29]=0x10;
    f[30]=2;assert(inspect_awdl(f,50,&o)==-EPROTONOSUPPORT);f[30]=3;
    f[28]=7;assert(inspect_awdl(f,50,&o)==-EPROTONOSUPPORT);f[28]=8;
    for (unsigned bit=1;bit<=128;bit<<=1) if (bit&0xc7) {
        f[1]=(unsigned char)bit;assert(inspect_awdl(f,50,&o)==-EBADMSG);
    }
    f[1]=8;assert(inspect_awdl(f,50,&o)==1);f[1]=0;
    f[22]=1;assert(inspect_awdl(f,50,&o)==-EBADMSG);f[22]=0;
    f[27]=0;assert(!inspect_awdl(f,50,&o));f[27]=0xf2;
    f[24]=4;assert(!inspect_awdl(f,50,&o));f[24]=127;
    f[0]=0x80;assert(!inspect_awdl(f,50,&o));
    struct sockaddr_ll from={.sll_ifindex=5,.sll_hatype=ARPHRD_IEEE80211_RADIOTAP};
    assert(awdl_rx_origin(&from,sizeof(from),5));
    from.sll_pkttype=PACKET_OUTGOING;assert(!awdl_rx_origin(&from,sizeof(from),5));
    from.sll_pkttype=PACKET_LOOPBACK;assert(!awdl_rx_origin(&from,sizeof(from),5));
    from.sll_pkttype=PACKET_MULTICAST;assert(awdl_rx_origin(&from,sizeof(from),5));
    assert(!awdl_rx_origin(&from,sizeof(from)-1,5));assert(!awdl_rx_origin(&from,sizeof(from),6));
    from.sll_hatype=ARPHRD_ETHER;assert(!awdl_rx_origin(&from,sizeof(from),5));
    puts("AWDL_OBSERVATION_MODEL_PASS_ONLY");
}
static void awdl_rx_accounting_tests(void) {
    unsigned char f[84];struct awdl_observation o;struct awdl_rx_stats stats={0};
    struct sockaddr_ll from;
    unsigned seen[RX_REASON_MAX]={0},packets=0;
#define RESET_RX() do { \
    memset(f,0,sizeof(f));f[2]=8;f[8]=0xd0;f[32]=127;f[34]=0x17;f[35]=0xf2;f[36]=8;f[37]=0x10; \
    from=(struct sockaddr_ll){.sll_ifindex=5,.sll_hatype=ARPHRD_IEEE80211_RADIOTAP,.sll_pkttype=PACKET_HOST}; \
} while (0)
#define CHECK_RX(size,n,capacity,want) do { \
    enum awdl_rx_reason reason=awdl_classify_rx(&from,size,5,f,n,capacity,&o,&stats); \
    assert(reason==(want));seen[reason]++;packets++; \
} while (0)
    RESET_RX();CHECK_RX(sizeof(from)-1,48,sizeof(f),RX_SHORT_ADDRESS);
    RESET_RX();from.sll_ifindex=6;CHECK_RX(sizeof(from),48,sizeof(f),RX_WRONG_INTERFACE);
    RESET_RX();from.sll_hatype=ARPHRD_ETHER;CHECK_RX(sizeof(from),48,sizeof(f),RX_WRONG_HARDWARE);
    RESET_RX();from.sll_pkttype=PACKET_OUTGOING;CHECK_RX(sizeof(from),48,sizeof(f),RX_OUTGOING);
    RESET_RX();from.sll_pkttype=PACKET_LOOPBACK;CHECK_RX(sizeof(from),48,sizeof(f),RX_OUTGOING);
    RESET_RX();from.sll_pkttype=255;CHECK_RX(sizeof(from),48,sizeof(f),RX_UNKNOWN_ORIGIN);
    RESET_RX();CHECK_RX(sizeof(from),85,sizeof(f),RX_PACKET_TRUNCATED);
    RESET_RX();f[0]=1;CHECK_RX(sizeof(from),48,sizeof(f),RX_RADIOTAP_ERROR);
    RESET_RX();f[5]=0x80;CHECK_RX(sizeof(from),48,sizeof(f),RX_TX_METADATA);
    RESET_RX();CHECK_RX(sizeof(from),9,sizeof(f),RX_SHORT_FRAME);
    RESET_RX();f[8]=0xd1;CHECK_RX(sizeof(from),48,sizeof(f),RX_BAD_FRAME_VERSION);
    RESET_RX();f[8]=0x80;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_ACTION);
    RESET_RX();f[8]=0x08;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_ACTION);
    RESET_RX();f[8]=0x04;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_ACTION);
    RESET_RX();f[32]=4;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_VENDOR_ACTION);
    RESET_RX();f[32]=3;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_VENDOR_ACTION);
    RESET_RX();CHECK_RX(sizeof(from),32,sizeof(f),RX_SHORT_FRAME);
    RESET_RX();CHECK_RX(sizeof(from),35,sizeof(f),RX_SHORT_FRAME);
    RESET_RX();f[35]=0;CHECK_RX(sizeof(from),48,sizeof(f),RX_NON_APPLE_VENDOR);
    RESET_RX();f[9]=0x40;CHECK_RX(sizeof(from),48,sizeof(f),RX_BAD_AWDL);
    RESET_RX();f[37]=0x20;CHECK_RX(sizeof(from),48,sizeof(f),RX_UNSUPPORTED_AWDL);
    RESET_RX();CHECK_RX(sizeof(from),48,sizeof(f),RX_OBSERVED);
    assert(o.subtype==0 && !o.tlvs);
    unsigned total=0;
    for (unsigned i=0;i<RX_REASON_MAX;i++) {assert(seen[i]>0);total+=seen[i];assert(awdl_rx_reason_names[i]);}
    assert(total==packets && stats.types[0]>0 && stats.types[1]==1 && stats.types[2]==1);
    assert(stats.mgmt_subtypes[8]==1 && stats.mgmt_subtypes[13]>0);
    assert(stats.public_actions==1 && stats.other_actions==1 && stats.vendor_actions>0);
    /* Every truncation of a valid packet is bounded; none can be observed. */
    for (size_t n=0;n<48;n++) {
        RESET_RX();assert(awdl_classify_rx(&from,sizeof(from),5,f,n,sizeof(f),&o,&stats)!=RX_OBSERVED);
    }
#undef RESET_RX
#undef CHECK_RX
    puts("AWDL_RX_ACCOUNTING_MODEL_PASS_ONLY");
}

static void awdl_parse_detail_tests(void) {
    unsigned char f[64];struct awdl_observation o;struct awdl_parse_detail d;
#define RESET_DETAIL() do {memset(f,0,sizeof(f));f[0]=0xd0;f[24]=127;f[26]=0x17;f[27]=0xf2;f[28]=8;f[29]=0x10;} while (0)
#define CHECK_DETAIL(n,ret,why) do {assert(inspect_awdl_detail(f,n,&o,&d)==ret);assert(d.reason==why);} while (0)
    RESET_DETAIL();CHECK_DETAIL(40,1,AWDL_PARSED);
    assert(d.protocol_fields_present && d.type==8 && d.version==16 && d.subtype==0 && d.bytes==40);
    RESET_DETAIL();f[24]=4;CHECK_DETAIL(40,0,AWDL_NOT_CANDIDATE);
    RESET_DETAIL();CHECK_DETAIL(FRAME_MAX+1,-EBADMSG,AWDL_OVERSIZE);
    RESET_DETAIL();f[1]=0x80;CHECK_DETAIL(40,-EBADMSG,AWDL_FRAME_FLAGS);assert(d.frame_control==0x80d0);
    RESET_DETAIL();f[22]=1;CHECK_DETAIL(40,-EBADMSG,AWDL_FRAGMENT);assert(d.fragment==1);
    RESET_DETAIL();CHECK_DETAIL(28,-EBADMSG,AWDL_SHORT_HEADER);assert(!d.protocol_fields_present);
    RESET_DETAIL();CHECK_DETAIL(39,-EBADMSG,AWDL_SHORT_HEADER);assert(d.protocol_fields_present);
    RESET_DETAIL();f[28]=9;CHECK_DETAIL(40,-EPROTONOSUPPORT,AWDL_OTHER_TYPE);
    RESET_DETAIL();f[29]=0x20;CHECK_DETAIL(40,-EPROTONOSUPPORT,AWDL_OTHER_VERSION);
    RESET_DETAIL();f[30]=7;CHECK_DETAIL(40,-EPROTONOSUPPORT,AWDL_OTHER_SUBTYPE);
    RESET_DETAIL();f[40]=4;f[41]=2;CHECK_DETAIL(44,-EBADMSG,AWDL_TLV_OVERRUN);
    assert(d.tlv_offset==40 && d.remaining==4 && d.tlv_length==2 && d.tlv_type==4 && d.tlv_length_present && !d.valid_tlvs);
    RESET_DETAIL();f[40]=4;f[41]=2;f[45]=0xaa;CHECK_DETAIL(46,-EBADMSG,AWDL_SHORT_TLV);
    assert(d.valid_tlvs==1 && d.tlv_offset==45 && d.remaining==1 && d.tlv_type==0xaa && !d.tlv_length_present && !d.tlv_length);
    assert(!o.tlvs); /* Diagnostics never publish partial TLVs as parsed success. */
    RESET_DETAIL();f[40]=4;f[41]=2;CHECK_DETAIL(45,1,AWDL_PARSED);assert(o.tlvs==1 && d.valid_tlvs==1);
    for (size_t n=0;n<40;n++) {RESET_DETAIL();assert(inspect_awdl_detail(f,n,&o,&d)!=1);}
    /* The first sample per reason is retained, rather than unbounded payload logging. */
    unsigned char packet[72]={0};packet[2]=8;RESET_DETAIL();f[1]=0x40;memcpy(packet+8,f,40);
    struct sockaddr_ll from={.sll_ifindex=5,.sll_hatype=ARPHRD_IEEE80211_RADIOTAP};struct awdl_rx_stats stats={0};
    assert(awdl_classify_rx(&from,sizeof(from),5,packet,48,sizeof(packet),&o,&stats)==RX_BAD_AWDL);
    memset(packet,0,sizeof(packet));packet[2]=8;memcpy(packet+8,f,41);
    assert(awdl_classify_rx(&from,sizeof(from),5,packet,49,sizeof(packet),&o,&stats)==RX_BAD_AWDL);
    assert(stats.candidate_reasons[AWDL_FRAME_FLAGS]==2 && stats.samples[AWDL_FRAME_FLAGS].bytes==40);
#undef RESET_DETAIL
#undef CHECK_DETAIL
    puts("AWDL_PARSE_DETAIL_MODEL_PASS_ONLY");
}

static void mgmt_event_message(struct message *m,unsigned index,unsigned freq,const unsigned char *frame,size_t n) {
    begin(m,25,NL80211_CMD_FRAME,0);
    assert(!add_attr(m,NL80211_ATTR_IFINDEX,&index,4));
    assert(!add_attr(m,NL80211_ATTR_WIPHY_FREQ,&freq,4));
    assert(!add_attr(m,NL80211_ATTR_FRAME,frame,n));
    ((struct nlmsghdr *)(void *)m->data)->nlmsg_len=(uint32_t)m->n;
}
static void awdl_mgmt_rx_tests(void) {
    struct client c={.family=25,.ifindex=24,.seq=8};struct message m;
    assert(!mgmt_register_message(&c,&m));
    struct bytes attrs={m.data+NLMSG_HDRLEN+GENL_HDRLEN,m.n-NLMSG_HDRLEN-GENL_HDRLEN},v;
    assert(m.data[NLMSG_HDRLEN]==NL80211_CMD_REGISTER_FRAME && c.seq==9);
    assert(attr(attrs,NL80211_ATTR_IFINDEX,&v)==1 && v.n==4 && u32(v.p)==24);
    assert(attr(attrs,NL80211_ATTR_FRAME_TYPE,&v)==1 && v.n==2 && u16(v.p)==0xd0);
    assert(attr(attrs,NL80211_ATTR_FRAME_MATCH,&v)==1 && v.n==5 && !memcmp(v.p,"\x7f\x00\x17\xf2\x08",5));
    assert(!attr(attrs,NL80211_ATTR_RECEIVE_MULTICAST,&v));
    unsigned char f[277]={0xd0};f[24]=127;f[26]=0x17;f[27]=0xf2;f[28]=8;f[29]=16;f[30]=3;f[40]=4;f[41]=234;
    struct mgmt_rx_stats s={0};mgmt_event_message(&m,24,5240,f,sizeof(f));
    assert(!mgmt_rx_datagram(&c,m.data,m.n,&s,false));
    assert(s.events==1 && s.parsed==1 && s.max_bytes==277 && s.over_256==1);
    assert(s.detail.candidate_reasons[AWDL_PARSED]==1);
    mgmt_event_message(&m,24,5240,f,256);assert(!mgmt_rx_datagram(&c,m.data,m.n,&s,false));
    assert(s.events==2 && s.malformed==1 && s.detail.candidate_reasons[AWDL_TLV_OVERRUN]==1);
    mgmt_event_message(&m,25,5240,f,sizeof(f));assert(!mgmt_rx_datagram(&c,m.data,m.n,&s,false) && s.ignored==1);
    mgmt_event_message(&m,24,0,f,sizeof(f));assert(!mgmt_rx_datagram(&c,m.data,m.n,&s,false) && s.malformed==2);
    mgmt_event_message(&m,24,5240,f,sizeof(f));assert(mgmt_rx_datagram(&c,m.data,m.n-1,&s,false)==-EBADMSG);
    f[28]=9;mgmt_event_message(&m,24,5240,f,sizeof(f));assert(!mgmt_rx_datagram(&c,m.data,m.n,&s,false) && s.ignored==2);
    puts("AWDL_NL80211_MGMT_RX_MODEL_PASS_ONLY");
}

int main(void) {
    awdl_mgmt_rx_tests();
    awdl_parse_detail_tests();
    awdl_rx_accounting_tests();
    awdl_observation_tests();
    request_error_tests();
    vendor_relay_tests();
    channel_tests();
    /* Kernel vendor replies append raw bytes and may omit final padding at
     * both attribute and netlink-message levels. Exercise every residue. */
    for (unsigned length=49;length<=52;length++) {
        unsigned char wire[WONDER_FB_HEADER+52]={0},frame[WONDER_FB_MAX];
        uint64_t owner=0x123456789ULL,token=0;size_t copied=0;
        wonder_fb_put(wire,WONDER_FB_VERSION);wonder_fb_put(wire+4,length);
        fbput64(wire+8,owner);fbput64(wire+16,7);action(wire+WONDER_FB_HEADER);
        struct client c={.family=25,.seq=7};struct message m;struct bytes reply,payload;
        begin(&m,25,NL80211_CMD_VENDOR,7);
        assert(!add_attr(&m,NL80211_ATTR_VENDOR_DATA,wire,WONDER_FB_HEADER+length));
        size_t padding=(4-length%4)%4;
        ((struct nlmsghdr *)(void *)m.data)->nlmsg_len=(uint32_t)m.n;
        assert(consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply)==1);
        assert(attr(reply,NL80211_ATTR_VENDOR_DATA,&payload)==1);
        assert(!feedback_packet(payload,owner,&token,frame,&copied) && copied==length && token==7);
        m.n-=padding;
        ((struct nlmsghdr *)(void *)m.data)->nlmsg_len=(uint32_t)m.n;
        assert(consume(&c,m.data,m.n,NL80211_CMD_VENDOR,&reply)==1);
        assert(attr(reply,NL80211_ATTR_VENDOR_DATA,&payload)==1);
        assert(!feedback_packet(payload,owner,&token,frame,&copied) && copied==length);
        assert(!memcmp(frame,wire+WONDER_FB_HEADER,length));
        assert(attr((struct bytes){reply.p,reply.n-1},NL80211_ATTR_VENDOR_DATA,&payload)==-EBADMSG);
        assert(consume(&c,m.data,m.n-1,NL80211_CMD_VENDOR,&reply)==-EBADMSG);
        if (padding>1) {
            assert(consume(&c,m.data,m.n+1,NL80211_CMD_VENDOR,&reply)==-EBADMSG);
            struct bytes attrs={m.data+NLMSG_HDRLEN+GENL_HDRLEN,m.n-NLMSG_HDRLEN-GENL_HDRLEN+1};
            assert(attr(attrs,NL80211_ATTR_VENDOR_DATA,&payload)==-EBADMSG);
        }
    }
    struct client capture_client={.family=25,.ifindex=34};struct message capture;
    assert(!capture_message(&capture_client,&capture,true));
    struct bytes capture_attrs={capture.data+NLMSG_HDRLEN+GENL_HDRLEN,capture.n-NLMSG_HDRLEN-GENL_HDRLEN};
    struct bytes data_rx,mgmt_rx,vendor_data,capture_cmd;
    assert(attr(capture_attrs,NL80211_ATTR_VENDOR_SUBCMD,&capture_cmd)==1 && u32(capture_cmd.p)==202);
    assert(attr(capture_attrs,NL80211_ATTR_VENDOR_DATA,&vendor_data)==1 && vendor_data.n==16);
    /* This is the flag rejected by the actual phone kernel when iw omitted it. */
    assert(u16(vendor_data.p-2)==(NL80211_ATTR_VENDOR_DATA|NLA_F_NESTED));
    assert(attr(vendor_data,2,&data_rx)==1 && data_rx.n==4 && u32(data_rx.p)==1);
    assert(attr(vendor_data,4,&mgmt_rx)==1 && mgmt_rx.n==4 && u32(mgmt_rx.p)==1);
    /* OCC must select RX management, data AND control, plus operating type 1.
     * No TX filter and no fallback request is emitted. Default LPC is unchanged. */
    assert(!capture_message_mode(&capture_client,&capture,true,true));
    capture_attrs=(struct bytes){capture.data+NLMSG_HDRLEN+GENL_HDRLEN,capture.n-NLMSG_HDRLEN-GENL_HDRLEN};
    assert(attr(capture_attrs,NL80211_ATTR_VENDOR_DATA,&vendor_data)==1 && vendor_data.n==32);
    for (unsigned kind=2;kind<=8;kind+=2) {
        struct bytes value;assert(attr(vendor_data,kind,&value)==1 && value.n==4 && u32(value.p)==1);
    }
    for (unsigned kind=1;kind<=7;kind+=2) {struct bytes absent;assert(!attr(vendor_data,kind,&absent));}
    assert(u16(vendor_data.p-2)==(NL80211_ATTR_VENDOR_DATA|NLA_F_NESTED));
    assert(!capture_message(&capture_client,&capture,false));
    capture_attrs=(struct bytes){capture.data+NLMSG_HDRLEN+GENL_HDRLEN,capture.n-NLMSG_HDRLEN-GENL_HDRLEN};
    assert(attr(capture_attrs,NL80211_ATTR_VENDOR_DATA,&vendor_data)==1 && !vendor_data.n);
    assert(u16(vendor_data.p-2)==NL80211_ATTR_VENDOR_DATA);
    assert(attr(capture_attrs,NL80211_ATTR_VENDOR_SUBCMD,&capture_cmd)==1 && u32(capture_cmd.p)==225);
    struct message state={0},response={0};unsigned state_value=0;bool capture_on=true;
    assert(!add_attr(&state,1,&state_value,4));assert(!add_attr(&response,NL80211_ATTR_VENDOR_DATA,state.data,state.n));
    assert(!capture_result((struct bytes){response.data,response.n},&capture_on) && !capture_on);
    state_value=1;state=(struct message){0};response=(struct message){0};
    assert(!add_attr(&state,1,&state_value,4));assert(!add_attr(&response,NL80211_ATTR_VENDOR_DATA,state.data,state.n));
    assert(!capture_result((struct bytes){response.data,response.n},&capture_on) && capture_on);
    assert(capture_result((struct bytes){response.data,response.n-1},&capture_on)==-EBADMSG);
    state_value=2;state=(struct message){0};response=(struct message){0};
    assert(!add_attr(&state,1,&state_value,4));assert(!add_attr(&response,NL80211_ATTR_VENDOR_DATA,state.data,state.n));
    assert(capture_result((struct bytes){response.data,response.n},&capture_on)==-EBADMSG);
    unsigned char payload[WONDER_FB_HEADER+25]={0},copy[WONDER_FB_MAX];
    uint64_t owner=0x1122334455667788ULL,token=0;size_t frame_length=0;
    wonder_fb_put(payload,WONDER_FB_VERSION);wonder_fb_put(payload+4,25);
    fbput64(payload+8,owner);fbput64(payload+16,9);action(payload+WONDER_FB_HEADER);
    assert(!feedback_packet((struct bytes){payload,sizeof(payload)},owner,&token,copy,&frame_length));
    assert(token==9 && frame_length==25 && !memcmp(copy,payload+WONDER_FB_HEADER,25));
    assert(feedback_packet((struct bytes){payload,sizeof(payload)},owner+1,&token,copy,&frame_length)==-EBADMSG);
    payload[28]=1;assert(feedback_packet((struct bytes){payload,sizeof(payload)},owner,&token,copy,&frame_length)==-EBADMSG);payload[28]=0;
    assert(feedback_packet((struct bytes){payload,sizeof(payload)-1},owner,&token,copy,&frame_length)==-EBADMSG);
    fbput64(payload+16,0);assert(feedback_packet((struct bytes){payload,sizeof(payload)},owner,&token,copy,&frame_length)==-EBADMSG);
    struct client queue_client={.family=25,.ifindex=7};struct message request_message;struct bytes field;
    assert(!feedback_message(&queue_client,&request_message,WONDER_FB_COMPLETE,owner,9,WONDER_FB_ACKED));
    struct bytes attrs={request_message.data+NLMSG_HDRLEN+GENL_HDRLEN,request_message.n-NLMSG_HDRLEN-GENL_HDRLEN};
    assert(attr(attrs,NL80211_ATTR_VENDOR_DATA,&field)==1 && field.n==WONDER_FB_HEADER);
    assert(fb64(field.p+8)==owner && fb64(field.p+16)==9 && wonder_fb_word(field.p+24)==WONDER_FB_ACKED);
    unsigned char f[128];action(f);
    f[25]=2;f[26]=0;f[27]=0;
    assert(!prepare_vendor_action(f,28,mac,false));
    f[24]=4;assert(prepare_vendor_action(f,28,mac,false)==-EOPNOTSUPP);action(f);
    unsigned char injected[FRAME_MAX+8];
    assert(injection_packet(injected,sizeof(injected),f,25,mac,false)==33);
    assert(injected[2]==8 && !memcmp(injected+8,f,25));
    assert(injection_packet(injected,32,f,25,mac,false)==-EMSGSIZE);
    f[10]++;assert(injection_packet(injected,sizeof(injected),f,25,mac,false)==-EADDRNOTAVAIL);
    assert(injection_packet(injected,sizeof(injected),f,25,mac,true)==33 && !memcmp(injected+18,mac,6));
    f[0]=8;assert(injection_packet(injected,sizeof(injected),f,25,mac,true)==-EOPNOTSUPP);action(f);
    assert(!prepare_frame(f,25,mac,false));
    assert(prepare_frame(f,24,mac,false)==-EMSGSIZE);
    f[0]=0x08;assert(prepare_frame(f,25,mac,false)==-EOPNOTSUPP);action(f);
    f[1]=0x40;assert(prepare_frame(f,25,mac,false)==-EOPNOTSUPP);action(f);
    f[22]=1;assert(prepare_frame(f,25,mac,false)==-EOPNOTSUPP);action(f);
    f[10]=3;assert(prepare_frame(f,25,mac,false)==-EADDRNOTAVAIL);
    assert(!prepare_frame(f,25,mac,true) && !memcmp(f+10,mac,6));
    /* Radiotap without flags, with FCS, BADFCS and extended present words. */
    unsigned char rt[128]={0};rt[2]=8;action(rt+8);size_t n=33;
    assert(!strip_radiotap(rt,&n) && n==25 && !memcmp(rt,f,25));
    memset(rt,0,sizeof(rt));rt[2]=9;rt[4]=2;rt[8]=0x10;action(rt+9);n=38;
    assert(!strip_radiotap(rt,&n) && n==25);
    memset(rt,0,sizeof(rt));rt[2]=9;rt[4]=2;rt[8]=0x40;action(rt+9);n=34;
    assert(strip_radiotap(rt,&n)==-EBADMSG);
    memset(rt,0,sizeof(rt));rt[2]=12;rt[7]=0x80;action(rt+12);n=37;
    assert(!strip_radiotap(rt,&n) && n==25);
    memset(rt,0,sizeof(rt));rt[2]=8;rt[7]=0x80;n=8;
    assert(strip_radiotap(rt,&n)==-EINVAL);
    /* Attribute alignment, zero-sized flags and malformed/duplicate lengths. */
    struct message m={0};uint64_t value=0x123456789abcdef0ULL;struct bytes a;
    assert(!add_attr(&m,17,&value,8) && !add_attr(&m,18,NULL,0));
    assert(attr((struct bytes){m.data,m.n},17,&a)==1 && a.n==8 && u64(a.p)==value);
    assert(attr((struct bytes){m.data,m.n},18,&a)==1 && !a.n);
    assert(!add_attr(&m,17,&value,8));assert(attr((struct bytes){m.data,m.n},17,&a)==-EBADMSG);
    m.data[0]=3;assert(attr((struct bytes){m.data,m.n},99,&a)==-EBADMSG);
    /* A netlink ACK is not a TX completion. An early status needs the exact
     * subsequent request cookie, interface AND frame except native sequence. */
    struct client c={.family=25,.seq=7,.ifindex=4,.frame=f,.frame_len=25};
    struct bytes reply;bool ack=false;
    struct nlmsghdr h={.nlmsg_len=NLMSG_HDRLEN+sizeof(struct nlmsgerr),.nlmsg_type=NLMSG_ERROR,.nlmsg_seq=7};
    struct nlmsgerr error={0};unsigned char ackbuf[NLMSG_HDRLEN+sizeof(error)]={0};
    memcpy(ackbuf,&h,NLMSG_HDRLEN);memcpy(ackbuf+NLMSG_HDRLEN,&error,sizeof(error));
    assert(!consume(&c,ackbuf,sizeof(ackbuf),NL80211_CMD_FRAME,&reply) && !c.have_cookie && !c.status_count);
    error.error=-EPERM;memcpy(ackbuf+NLMSG_HDRLEN,&error,sizeof(error));
    assert(consume(&c,ackbuf,sizeof(ackbuf),NL80211_CMD_FRAME,&reply)==-EPERM);
    status_message(&m,5,9,f,25,true);assert(!consume(&c,m.data,m.n,NL80211_CMD_FRAME,&reply) && !c.status_count);
    unsigned char wrong[25];memcpy(wrong,f,25);wrong[24]++;
    status_message(&m,4,9,wrong,25,true);assert(!consume(&c,m.data,m.n,NL80211_CMD_FRAME,&reply) && !c.status_count);
    memcpy(wrong,f,25);wrong[22]=0xb0;wrong[23]=0xa5;
    assert(status_frame_matches((struct bytes){wrong,25},f,25));
    status_message(&m,4,9,wrong,25,true);
    assert(!consume(&c,m.data,m.n,NL80211_CMD_FRAME,&reply) && c.status_count==1);
    assert(!matching_status(&c,&ack));
    c.have_cookie=true;c.cookie=10;assert(!matching_status(&c,&ack));
    c.cookie=9;assert(matching_status(&c,&ack) && ack);
    c.have_cookie=false;c.status_count=0;
    wrong[22]|=1;assert(!status_frame_matches((struct bytes){wrong,25},f,25));
    wrong[22]&=0xf0;wrong[10]^=1;assert(!status_frame_matches((struct bytes){wrong,25},f,25));
    wrong[10]^=1;wrong[2]^=1;assert(!status_frame_matches((struct bytes){wrong,25},f,25));
    assert(!status_frame_matches((struct bytes){wrong,24},f,25));
    status_message(&m,4,9,f,25,true);assert(!consume(&c,m.data,m.n,NL80211_CMD_FRAME,&reply));
    assert(c.status_count==1 && !matching_status(&c,&ack));
    c.have_cookie=true;c.cookie=10;assert(!matching_status(&c,&ack));
    c.cookie=9;assert(matching_status(&c,&ack) && ack);
    c.status_count=0;status_message(&m,4,9,f,25,false);
    assert(!consume(&c,m.data,m.n,NL80211_CMD_FRAME,&reply) && matching_status(&c,&ack) && !ack);
    assert(consume(&c,m.data,m.n-1,NL80211_CMD_FRAME,&reply)==-EBADMSG);
    /* Cookie reply and early status in one datagram are both processed. */
    c.status_count=0;c.have_cookie=false;struct message cookie;
    begin(&cookie,25,NL80211_CMD_FRAME,7);assert(!add_attr(&cookie,NL80211_ATTR_COOKIE,&value,8));
    ((struct nlmsghdr *)(void *)cookie.data)->nlmsg_len=(uint32_t)cookie.n;
    status_message(&m,4,value,f,25,true);unsigned char both[16384];
    memcpy(both,cookie.data,cookie.n);memcpy(both+cookie.n,m.data,m.n);
    assert(consume(&c,both,cookie.n+m.n,NL80211_CMD_FRAME,&reply)==1);
    assert(attr(reply,NL80211_ATTR_COOKIE,&a)==1);c.cookie=u64(a.p);c.have_cookie=true;
    assert(matching_status(&c,&ack) && ack);
    unsigned char raw[34]={0x88};memset(raw+4,0xff,6);memcpy(raw+10,mac,6);raw[26]=0xaa;
    assert(!prepare_raw_frame(raw,sizeof(raw),mac,false));
    raw[10]++;assert(prepare_raw_frame(raw,sizeof(raw),mac,false)==-EADDRNOTAVAIL);
    assert(!prepare_raw_frame(raw,sizeof(raw),mac,true));
    raw[1]=0x40;assert(prepare_raw_frame(raw,sizeof(raw),mac,false)==-EOPNOTSUPP);raw[1]=0;
    raw[24]=0x80;assert(prepare_raw_frame(raw,sizeof(raw),mac,false)==-EOPNOTSUPP);raw[24]=0;
    unsigned char wire[MISHARE_RAW_HEADER]={0};mishare_raw_set_word(wire,1);mishare_raw_set_word(wire+8,sizeof(raw));
    assert(mishare_raw_word(wire)==1 && mishare_raw_word(wire+8)==sizeof(raw));
    /* Unified relay selects exactly one transport and retains both modes'
     * frame/source restrictions. RX packet exclusion remains in capture loop. */
    bool use_raw=true;action(f);raw[24]=0;
    assert(!prepare_relay_frame(false,true,f,25,mac,false,&use_raw) && !use_raw);
    assert(!prepare_relay_frame(false,true,raw,sizeof(raw),mac,false,&use_raw) && use_raw);
    assert(prepare_relay_frame(false,false,raw,sizeof(raw),mac,false,&use_raw)==-EOPNOTSUPP);
    assert(prepare_relay_frame(true,false,f,25,mac,false,&use_raw)==-EOPNOTSUPP);
    f[0]=0x40;assert(prepare_relay_frame(false,true,f,25,mac,false,&use_raw)==-EOPNOTSUPP);action(f);
    f[10]++;assert(prepare_relay_frame(false,true,f,25,mac,false,&use_raw)==-EADDRNOTAVAIL);
    assert(!prepare_relay_frame(false,true,f,25,mac,true,&use_raw) && !use_raw);
    unsigned parsed;assert(!number("5180",2300,5900,&parsed) && parsed==5180);
    assert(number("5180x",2300,5900,&parsed)==-EINVAL);
    puts("ACTION_TX_PROTOCOL_TEST_PASS_ONLY");return 0;
}
