// SPDX-License-Identifier: GPL-2.0-only
#define ACTION_TX_TEST
#include "../native/wireless/action_tx.c"
#include <assert.h>

static unsigned char mac[6]={2,1,2,3,4,5};
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
    unsigned char f[128];action(f);
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
     * subsequent request cookie, interface AND original frame. */
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
    unsigned parsed;assert(!number("5180",2300,5900,&parsed) && parsed==5180);
    assert(number("5180x",2300,5900,&parsed)==-EINVAL);
    puts("ACTION_TX_PROTOCOL_TEST_PASS_ONLY");return 0;
}
