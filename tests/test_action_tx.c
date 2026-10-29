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
static void status_message(struct message *m,unsigned index,uint64_t cookie,
                           const unsigned char *frame,size_t len,bool ack) {
    begin(m,25,NL80211_CMD_FRAME_TX_STATUS,0);
    assert(!add_attr(m,NL80211_ATTR_IFINDEX,&index,4));
    assert(!add_attr(m,NL80211_ATTR_COOKIE,&cookie,8));
    assert(!add_attr(m,NL80211_ATTR_FRAME,frame,len));
    if (ack) assert(!add_attr(m,NL80211_ATTR_ACK,NULL,0));
    ((struct nlmsghdr *)(void *)m->data)->nlmsg_len=(uint32_t)m->n;
}
int main(void) {
    request_error_tests();
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
