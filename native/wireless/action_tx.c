// SPDX-License-Identifier: GPL-2.0-only
/* Experimental Action-frame TX through the native nl80211 driver.
 * One outstanding request; netlink acceptance is never reported as RF success.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/genetlink.h>
#include <net/if_arp.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <linux/netlink.h>
#include <linux/nl80211.h>
#include <net/if.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define FRAME_MAX 2304
#define MESSAGE_MAX 65536
#define STATUS_MAX 8
struct bytes { const unsigned char *p; size_t n; };
struct message { unsigned char data[8192]; size_t n; };
struct tx_status { uint64_t cookie; bool ack; };
struct client {
    int fd;
    uint16_t family;
    uint32_t seq;
    unsigned ifindex;
    const unsigned char *frame;
    size_t frame_len;
    struct tx_status statuses[STATUS_MAX];
    unsigned status_count;
    uint64_t cookie;
    bool have_cookie;
};
static volatile sig_atomic_t interrupted;
static void on_signal(int signal_number) { (void)signal_number; interrupted = 1; }
static uint16_t u16(const void *p) { uint16_t n; memcpy(&n,p,2); return n; }
static uint32_t u32(const void *p) { uint32_t n; memcpy(&n,p,4); return n; }
static uint64_t u64(const void *p) { uint64_t n; memcpy(&n,p,8); return n; }
static size_t align4(size_t n) { return (n+3U)&~3U; }
static int64_t now_ms(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) return -1;
    return (int64_t)t.tv_sec*1000+t.tv_nsec/1000000;
}
static int wait_read(int fd,int64_t deadline) {
    for (;;) {
        int64_t remaining=deadline-now_ms();
        if (interrupted) return -EINTR;
        if (remaining<=0) return -ETIMEDOUT;
        struct pollfd p={.fd=fd,.events=POLLIN};
        int ret=poll(&p,1,(int)remaining);
        if (ret<0 && errno==EINTR) continue;
        if (ret<0) return -errno;
        if (!ret) return -ETIMEDOUT;
        if (p.revents&POLLIN) return 0;
        return -EIO;
    }
}
/* Validates every attribute, including the final one. */
static int attr(struct bytes attrs,unsigned type,struct bytes *found) {
    bool have=false;
    *found=(struct bytes){0};
    while (attrs.n) {
        if (attrs.n<sizeof(struct nlattr)) return -EBADMSG;
        unsigned len=u16(attrs.p),kind=u16(attrs.p+2)&NLA_TYPE_MASK;
        if (len<sizeof(struct nlattr) || len>attrs.n || align4(len)>attrs.n) return -EBADMSG;
        if (kind==type) {
            if (have) return -EBADMSG;
            *found=(struct bytes){attrs.p+4,len-4};have=true;
        }
        attrs.p+=align4(len);attrs.n-=align4(len);
    }
    return have?1:0;
}
static int add_attr(struct message *m,unsigned type,const void *data,size_t len) {
    size_t size=4+len,padded=align4(size);
    if (size>UINT16_MAX || m->n+padded>sizeof(m->data)) return -EMSGSIZE;
    struct nlattr a={.nla_len=(uint16_t)size,.nla_type=(uint16_t)type};
    memcpy(m->data+m->n,&a,4);
    if (len) memcpy(m->data+m->n+4,data,len);
    memset(m->data+m->n+size,0,padded-size);m->n+=padded;return 0;
}
static void begin(struct message *m,unsigned family,unsigned command,uint32_t seq) {
    struct nlmsghdr h={.nlmsg_len=NLMSG_HDRLEN+GENL_HDRLEN,.nlmsg_type=(uint16_t)family,
        .nlmsg_flags=NLM_F_REQUEST|NLM_F_ACK,.nlmsg_seq=seq};
    struct genlmsghdr g={.cmd=(uint8_t)command,.version=1};
    memset(m,0,sizeof(*m));memcpy(m->data,&h,NLMSG_HDRLEN);
    memcpy(m->data+NLMSG_HDRLEN,&g,GENL_HDRLEN);m->n=h.nlmsg_len;
}
static int transmit(struct client *c,struct message *m) {
    struct sockaddr_nl kernel={.nl_family=AF_NETLINK};
    ((struct nlmsghdr *)(void *)m->data)->nlmsg_len=(uint32_t)m->n;
    ssize_t n=sendto(c->fd,m->data,m->n,0,(void *)&kernel,sizeof(kernel));
    return n<0?-errno:(size_t)n==m->n?0:-EIO;
}
static int receive(struct client *c,unsigned char *buffer,size_t size,int64_t deadline) {
    int ret=wait_read(c->fd,deadline);if (ret) return ret;
    struct sockaddr_nl peer={0};struct iovec iov={buffer,size};
    struct msghdr m={.msg_name=&peer,.msg_namelen=sizeof(peer),.msg_iov=&iov,.msg_iovlen=1};
    ssize_t n=recvmsg(c->fd,&m,0);
    if (n<0) return -errno;
    if ((m.msg_flags&MSG_TRUNC) || m.msg_namelen<sizeof(peer) || peer.nl_family!=AF_NETLINK || peer.nl_pid) return -EBADMSG;
    return n>0?(int)n:-EIO;
}
/* Status may arrive before the command's cookie reply. Buffer only exact
 * interface/frame events, then match the cookie supplied by the command. */
static int record_status(struct client *c,struct bytes attrs) {
    struct bytes id,cookie,frame,ack;
    if (attr(attrs,NL80211_ATTR_IFINDEX,&id)!=1 || id.n!=4 || u32(id.p)!=c->ifindex) return 0;
    if (attr(attrs,NL80211_ATTR_FRAME,&frame)!=1 || frame.n!=c->frame_len || !c->frame || memcmp(frame.p,c->frame,frame.n)) return 0;
    if (attr(attrs,NL80211_ATTR_COOKIE,&cookie)!=1 || cookie.n!=8) return -EBADMSG;
    int have_ack=attr(attrs,NL80211_ATTR_ACK,&ack);
    if (have_ack<0 || (have_ack && ack.n)) return -EBADMSG;
    if (c->status_count>=STATUS_MAX) return -ENOBUFS;
    c->statuses[c->status_count++]=(struct tx_status){u64(cookie.p),have_ack==1};return 0;
}
static int matching_status(struct client *c,bool *acked) {
    if (!c->have_cookie) return 0;
    for (unsigned i=0;i<c->status_count;i++) if (c->statuses[i].cookie==c->cookie) {
        *acked=c->statuses[i].ack;return 1;
    }
    return 0;
}
/* Returns 1 for a matching generic reply, 0 for ACK/unrelated traffic. */
static int consume(struct client *c,const unsigned char *data,size_t len,unsigned expected_command,
                   struct bytes *reply) {
    bool found=false;*reply=(struct bytes){0};
    while (len) {
        if (len<NLMSG_HDRLEN) return -EBADMSG;
        struct nlmsghdr h;memcpy(&h,data,sizeof(h));
        if (h.nlmsg_len<NLMSG_HDRLEN || h.nlmsg_len>len || align4(h.nlmsg_len)>len) return -EBADMSG;
        const unsigned char *body=data+NLMSG_HDRLEN;size_t n=h.nlmsg_len-NLMSG_HDRLEN;
        if (h.nlmsg_type==NLMSG_ERROR) {
            if (n<sizeof(struct nlmsgerr)) return -EBADMSG;
            int error;memcpy(&error,body,4);
            if (h.nlmsg_seq==c->seq && error) return error<0?error:-EBADMSG;
        } else if (h.nlmsg_type==c->family || h.nlmsg_type==GENL_ID_CTRL) {
            if (n<GENL_HDRLEN) return -EBADMSG;
            unsigned cmd=body[0];struct bytes attrs={body+GENL_HDRLEN,n-GENL_HDRLEN};
            if (h.nlmsg_type==c->family && cmd==NL80211_CMD_FRAME_TX_STATUS && c->frame) {
                int ret=record_status(c,attrs);if (ret) return ret;
            }
            if (h.nlmsg_type==c->family && h.nlmsg_seq==c->seq && cmd==expected_command) {
                if (found) return -EBADMSG;
                *reply=attrs;found=true;
            }
        }
        size_t step=align4(h.nlmsg_len);data+=step;len-=step;
    }
    return found?1:0;
}
static int request(struct client *c,struct message *m,unsigned command,
                   unsigned char *buffer,struct bytes *reply,int timeout_ms) {
    int ret=transmit(c,m);if (ret) return ret;
    int64_t deadline=now_ms()+timeout_ms;
    for (;;) {
        ret=receive(c,buffer,MESSAGE_MAX,deadline);if (ret<0) return ret;
        ret=consume(c,buffer,(size_t)ret,command,reply);
        if (ret<0) return ret;
        if (ret==1) return 0;
    }
}
static int connect_nl(struct client *c) {
    unsigned char buffer[MESSAGE_MAX];struct bytes reply,id,groups;
    memset(c,0,sizeof(*c));c->fd=-1;c->family=GENL_ID_CTRL;
    c->fd=socket(AF_NETLINK,SOCK_RAW|SOCK_CLOEXEC,NETLINK_GENERIC);
    if (c->fd<0) return -errno;
    struct sockaddr_nl addr={.nl_family=AF_NETLINK};
    if (bind(c->fd,(void *)&addr,sizeof(addr))) return -errno;
    struct message m;begin(&m,GENL_ID_CTRL,CTRL_CMD_GETFAMILY,++c->seq);
    int ret=add_attr(&m,CTRL_ATTR_FAMILY_NAME,"nl80211",8);if (ret) return ret;
    /* CTRL_CMD_GETFAMILY replies with CTRL_CMD_NEWFAMILY. */
    ret=request(c,&m,CTRL_CMD_NEWFAMILY,buffer,&reply,3000);if (ret) return ret;
    if (attr(reply,CTRL_ATTR_FAMILY_ID,&id)!=1 || id.n!=2) return -EBADMSG;
    c->family=u16(id.p);
    if (attr(reply,CTRL_ATTR_MCAST_GROUPS,&groups)!=1) return -ENOENT;
    while (groups.n) {
        if (groups.n<4) return -EBADMSG;
        unsigned n=u16(groups.p);
        if (n<4 || align4(n)>groups.n) return -EBADMSG;
        struct bytes group={groups.p+4,n-4},name,group_id;
        if (attr(group,CTRL_ATTR_MCAST_GRP_NAME,&name)==1 && name.n==5 && !memcmp(name.p,"mlme",5)) {
            if (attr(group,CTRL_ATTR_MCAST_GRP_ID,&group_id)!=1 || group_id.n!=4) return -EBADMSG;
            unsigned value=u32(group_id.p);
            if (setsockopt(c->fd,SOL_NETLINK,NETLINK_ADD_MEMBERSHIP,&value,sizeof(value))) return -errno;
            return 0;
        }
        groups.p+=align4(n);groups.n-=align4(n);
    }
    return -ENOENT;
}
static int strip_radiotap(unsigned char *frame,size_t *length) {
    size_t n=*length;
    if (n<8 || frame[0] || frame[1]) return -EINVAL;
    unsigned rt=(unsigned)frame[2]|((unsigned)frame[3]<<8);
    if (rt<8 || rt>n) return -EINVAL;
    size_t at=4;uint32_t first=u32(frame+4),present;
    unsigned words=0;
    do {
        if (at+4>rt || ++words>8) return -EINVAL;
        present=u32(frame+at);at+=4;
    } while (present&(1U<<31));
    if (first&1U) { at=(at+7U)&~7U;if (at+8>rt) return -EINVAL;at+=8; }
    if (first&2U) {
        if (at>=rt) return -EINVAL;
        unsigned flags=frame[at];
        if (flags&0x40) return -EBADMSG; /* radiotap BADFCS */
        if (flags&0x10) {if (n<rt+4) return -EINVAL;n-=4;}
    }
    memmove(frame,frame+rt,n-rt);*length=n-rt;return 0;
}
static int prepare_frame(unsigned char *frame,size_t length,const unsigned char mac[6],bool rewrite) {
    if (length<25 || length>FRAME_MAX) return -EMSGSIZE;
    unsigned fc=(unsigned)frame[0]|((unsigned)frame[1]<<8);
    /* Unprotected, unfragmented Action frames with a conventional 24-byte header. */
    if ((fc&0x00ff)!=0x00d0 || (fc&(0x0300|0x0400|0x4000|0x8000)) || (frame[22]&15)) return -EOPNOTSUPP;
    if (memcmp(frame+10,mac,6)) {
        if (!rewrite) return -EADDRNOTAVAIL;
        memcpy(frame+10,mac,6);
    }
    return 0;
}
static int native_interface(const char *name,unsigned *index,unsigned char mac[6]) {
    if (strlen(name)>=IFNAMSIZ) return -ENAMETOOLONG;
    *index=if_nametoindex(name);if (!*index) return -ENODEV;
    int fd=socket(AF_INET,SOCK_DGRAM|SOCK_CLOEXEC,0);if (fd<0) return -errno;
    struct ifreq r={0};memcpy(r.ifr_name,name,strlen(name)+1);
    int ret=0;
    if (ioctl(fd,SIOCGIFFLAGS,&r)) ret=-errno;
    else if (!(r.ifr_flags&IFF_UP)) ret=-ENETDOWN;
    else if (ioctl(fd,SIOCGIFHWADDR,&r)) ret=-errno;
    else if (r.ifr_hwaddr.sa_family!=ARPHRD_ETHER) ret=-EOPNOTSUPP;
    else memcpy(mac,r.ifr_hwaddr.sa_data,6);
    close(fd);return ret;
}
static int action_tx(struct client *c,unsigned freq,const unsigned char *frame,size_t len,int timeout_ms) {
    unsigned char buffer[MESSAGE_MAX];struct bytes reply,cookie;struct message m;
    c->frame=frame;c->frame_len=len;c->status_count=0;c->have_cookie=false;
    begin(&m,c->family,NL80211_CMD_FRAME,++c->seq);
    int ret=add_attr(&m,NL80211_ATTR_IFINDEX,&c->ifindex,4);
    if (!ret) ret=add_attr(&m,NL80211_ATTR_WIPHY_FREQ,&freq,4);
    if (!ret) ret=add_attr(&m,NL80211_ATTR_FRAME,frame,len);
    if (ret) return ret;
    ret=request(c,&m,NL80211_CMD_FRAME,buffer,&reply,timeout_ms);if (ret) return ret;
    if (attr(reply,NL80211_ATTR_COOKIE,&cookie)!=1 || cookie.n!=8) return -EBADMSG;
    c->cookie=u64(cookie.p);c->have_cookie=true;
    printf("{\"event\":\"submitted\",\"cookie\":\"%" PRIu64 "\",\"bytes\":%zu,\"freq\":%u}\n",c->cookie,len,freq);fflush(stdout);
    int64_t deadline=now_ms()+timeout_ms;bool acked=false;
    while (!matching_status(c,&acked)) {
        ret=receive(c,buffer,sizeof(buffer),deadline);if (ret<0) return ret;
        ret=consume(c,buffer,(size_t)ret,NL80211_CMD_FRAME,&reply);if (ret<0) return ret;
    }
    bool group=(frame[4]&1)!=0;
    printf("{\"event\":\"tx_status\",\"cookie\":\"%" PRIu64 "\",\"acked\":%s,\"group_destination\":%s}\n",c->cookie,acked?"true":"false",group?"true":"false");fflush(stdout);
    c->frame=NULL;
    return acked||group?0:-ENOMSG;
}
static int number(const char *s,unsigned min,unsigned max,unsigned *out) {
    char *end;errno=0;unsigned long value=strtoul(s,&end,10);
    if (errno || !*s || *end || value<min || value>max) return -EINVAL;
    *out=(unsigned)value;return 0;
}
static void usage(void) {
    puts("action-tx send --dev wlan0 --freq MHz --frame FILE [--radiotap] [--rewrite-source] [--timeout-ms 3000]\n"
         "action-tx relay --listen wonder0 --dev wlan0 --freq MHz [--rewrite-source] [--max-frames 1] [--seconds 30]\n"
         "Root required. Action frames only, on-channel native TX. No automatic retries.\n"
         "A submitted cookie is not a TX status; group frames have no peer ACK guarantee.");
}
#ifndef ACTION_TX_TEST
int main(int argc,char **argv) {
    const char *mode=argc>1?argv[1]:"",*dev=NULL,*listen_dev=NULL,*file=NULL;
    bool radiotap=false,rewrite=false;unsigned freq=0,timeout=3000,limit=1,seconds=30;
    if (!strcmp(mode,"--help") || !strcmp(mode,"help")) {usage();return 0;}
    if (strcmp(mode,"send") && strcmp(mode,"relay")) {usage();return 2;}
    bool relay=!strcmp(mode,"relay");
    for (int i=2;i<argc;i++) {
        const char *arg=argv[i];
        if (!strcmp(arg,"--radiotap")) radiotap=true;
        else if (!strcmp(arg,"--rewrite-source")) rewrite=true;
        else {
            if (++i>=argc) {usage();return 2;}
            if (!strcmp(arg,"--dev")) dev=argv[i];
            else if (!strcmp(arg,"--listen")) listen_dev=argv[i];
            else if (!strcmp(arg,"--frame")) file=argv[i];
            else if (!strcmp(arg,"--freq")) {if (number(argv[i],2300,5900,&freq)) return 2;}
            else if (!strcmp(arg,"--timeout-ms")) {if (number(argv[i],100,10000,&timeout)) return 2;}
            else if (!strcmp(arg,"--max-frames")) {if (number(argv[i],1,100000,&limit)) return 2;}
            else if (!strcmp(arg,"--seconds")) {if (number(argv[i],1,86400,&seconds)) return 2;}
            else {usage();return 2;}
        }
    }
    if (!dev || !freq || (relay?(!listen_dev || file || radiotap || !strcmp(dev,listen_dev)):(!file || listen_dev))) {usage();return 2;}
    signal(SIGINT,on_signal);signal(SIGTERM,on_signal);
    struct client c={.fd=-1};unsigned ifindex;unsigned char mac[6];
    int ret=native_interface(dev,&ifindex,mac);if (ret) goto done;
    ret=connect_nl(&c);if (ret) goto done;c.ifindex=ifindex;
    if (!relay) {
        unsigned char frame[8192];FILE *f=fopen(file,"rb");
        if (!f) {ret=-errno;goto done;}
        size_t n=fread(frame,1,sizeof(frame),f);bool bad=ferror(f) || !feof(f);fclose(f);
        if (bad) {ret=-EMSGSIZE;goto done;}
        if (radiotap) {ret=strip_radiotap(frame,&n);if (ret) goto done;}
        ret=prepare_frame(frame,n,mac,rewrite);if (ret) goto done;
        ret=action_tx(&c,freq,frame,n,(int)timeout);
    } else {
        unsigned index=if_nametoindex(listen_dev);if (!index) {ret=-ENODEV;goto done;}
        int capture=socket(AF_PACKET,SOCK_RAW|SOCK_CLOEXEC,htons(ETH_P_ALL));
        if (capture<0) {ret=-errno;goto done;}
        struct sockaddr_ll addr={.sll_family=AF_PACKET,.sll_protocol=htons(ETH_P_ALL),.sll_ifindex=(int)index};
        if (bind(capture,(void *)&addr,sizeof(addr))) {ret=-errno;close(capture);goto done;}
        unsigned sent=0,failed=0,ignored=0,source_mismatch=0;int64_t deadline=now_ms()+(int64_t)seconds*1000;
        puts("{\"event\":\"relay_ready\",\"mode\":\"action_frames_only\"}");fflush(stdout);
        while (sent+failed<limit && !interrupted) {
            ret=wait_read(capture,deadline);if (ret) break;
            unsigned char frame[8192];struct sockaddr_ll from={0};socklen_t size=sizeof(from);
            ssize_t n=recvfrom(capture,frame,sizeof(frame),MSG_TRUNC,(void *)&from,&size);
            if (n<0) {ret=-errno;break;}
            if (n>(ssize_t)sizeof(frame) || size<sizeof(from) || from.sll_ifindex!=(int)index || from.sll_pkttype!=PACKET_OUTGOING) {ignored++;continue;}
            size_t length=(size_t)n;
            ret=strip_radiotap(frame,&length);if (ret) {ignored++;continue;}
            ret=prepare_frame(frame,length,mac,rewrite);
            if (ret) {
                if (ret==-EADDRNOTAVAIL && ++source_mismatch==1)
                    fprintf(stderr,"relay: source MAC differs from native interface; --rewrite-source is explicit and changes protocol identity\n");
                ignored++;continue;
            }
            ret=action_tx(&c,freq,frame,length,(int)timeout);
            if (ret) {failed++;fprintf(stderr,"{\"event\":\"tx_error\",\"errno\":%d}\n",-ret);} else sent++;
        }
        close(capture);
        printf("{\"event\":\"relay_summary\",\"completed\":%u,\"failed\":%u,\"ignored\":%u,\"source_mismatch\":%u}\n",sent,failed,ignored,source_mismatch);
        ret=failed?-EIO:sent?0:ret?ret:-ENODATA;
    }
done:
    if (c.fd>=0) close(c.fd);
    if (ret) {fprintf(stderr,"action-tx: %s (%d); no retry performed\n",strerror(-ret),-ret);return 1;}
    return 0;
}
#endif
