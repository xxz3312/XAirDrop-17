// SPDX-License-Identifier: GPL-2.0-only
#include <linux/capability.h>
#include <linux/etherdevice.h>
#include <linux/module.h>
#include <linux/random.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/ktime.h>
#include "core.h"
#include "feedback.h"
#include "feedback_protocol.h"
#include "feedback_state.h"

bool wonder_external_tx;
module_param_named(external_tx, wonder_external_tx, bool, 0444);
MODULE_PARM_DESC(external_tx, "Opt-in token TX/completion queue for external monitor mode");
struct wonder_feedback {
    spinlock_t lock;
    struct delayed_work work;
    struct wonder_data *wonder;
    struct wonder_fb_state state;
};
static u64 fb_now(void) { return ktime_get_boottime_ns()/NSEC_PER_MSEC; }
static u64 fb_u64(const unsigned char *p)
{
    return (u64)wonder_fb_word(p) | (u64)wonder_fb_word(p+4)<<32;
}
static void fb_put64(unsigned char *p,u64 n)
{
    wonder_fb_put(p,n);wonder_fb_put(p+4,n>>32);
}
static void fb_report(struct wonder_feedback *f,struct sk_buff *skb,unsigned outcome)
{
    struct ieee80211_tx_info *info=IEEE80211_SKB_CB(skb);
    bool group=skb->len>=10 && is_multicast_ether_addr(skb->data+4);
    bool noack=info->flags & IEEE80211_TX_CTL_NO_ACK;
    unsigned evidence=wonder_fb_evidence(outcome,noack,group);
    ieee80211_tx_info_clear_status(info);
    info->flags &= ~(IEEE80211_TX_STAT_ACK | IEEE80211_TX_STAT_NOACK_TRANSMITTED);
    /* RAW success does not provide peer-ACK evidence. Never invent signal,
     * retry count or rates. Group/NO_ACK success gets NOACK_TRANSMITTED only. */
    if (evidence==WONDER_FB_ACKED)
        info->flags |= IEEE80211_TX_STAT_ACK;
    else if (evidence==WONDER_FB_NOACK)
        info->flags |= IEEE80211_TX_STAT_NOACK_TRANSMITTED;
    ieee80211_tx_status_irqsafe(f->wonder->hw,skb);
}
static void fb_sweep(struct wonder_feedback *f,bool stop)
{
    struct sk_buff *packets[WONDER_FB_SLOTS];
    unsigned long flags;int count,i;u64 now=fb_now();
    spin_lock_irqsave(&f->lock,flags);
    if (stop) {f->state.running=0;f->state.owner=0;}
    count=wonder_fb_sweep(&f->state,now,(void **)packets);
    spin_unlock_irqrestore(&f->lock,flags);
    for (i=0;i<count;i++) fb_report(f,packets[i],WONDER_FB_FAILED);
}
static void fb_work(struct work_struct *work)
{
    struct wonder_feedback *f=container_of(to_delayed_work(work),struct wonder_feedback,work);
    unsigned long flags;
    fb_sweep(f,false);
    spin_lock_irqsave(&f->lock,flags);
    if (f->state.running && !f->state.closing)
        schedule_delayed_work(&f->work,msecs_to_jiffies(250));
    spin_unlock_irqrestore(&f->lock,flags);
}
int wonder_feedback_init(struct wonder_data *wonder)
{
    struct wonder_feedback *f;
    if (!wonder_external_tx) return 0;
    if (!wonder_external_monitor) return -EINVAL;
    f=kzalloc(sizeof(*f),GFP_KERNEL);if (!f) return -ENOMEM;
    spin_lock_init(&f->lock);INIT_DELAYED_WORK(&f->work,fb_work);f->wonder=wonder;
    /* Lifetime-scoped randomized starting token; never reset on link cycling.
     * Counter exhaustion refuses new packets rather than reusing a token. */
    f->state.next_token=get_random_u64() | 1ULL;
    wonder->feedback=f;return 0;
}
void wonder_feedback_start(struct wonder_data *wonder)
{
    struct wonder_feedback *f=wonder->feedback;unsigned long flags;
    if (!f) return;
    spin_lock_irqsave(&f->lock,flags);
    if (!f->state.closing) {
        f->state.running=1;
        schedule_delayed_work(&f->work,msecs_to_jiffies(250));
    }
    spin_unlock_irqrestore(&f->lock,flags);
}
void wonder_feedback_stop(struct wonder_data *wonder)
{
    struct wonder_feedback *f=wonder->feedback;
    if (!f) return;
    fb_sweep(f,true);cancel_delayed_work_sync(&f->work);
}
void wonder_feedback_shutdown(struct wonder_data *wonder)
{
    struct wonder_feedback *f=wonder->feedback;unsigned long flags;
    if (!f) return;
    spin_lock_irqsave(&f->lock,flags);f->state.closing=1;spin_unlock_irqrestore(&f->lock,flags);
    wonder_feedback_stop(wonder);
}
void wonder_feedback_free(struct wonder_data *wonder)
{
    kfree(wonder->feedback);wonder->feedback=NULL;
}
void wonder_feedback_tx(struct wonder_data *wonder,struct sk_buff *skb)
{
    struct wonder_feedback *f=wonder->feedback;unsigned long flags;int accepted=0;
    if (!f) {ieee80211_free_txskb(wonder->hw,skb);return;}
    spin_lock_irqsave(&f->lock,flags);
    if (skb->len>=24 && skb->len<=WONDER_FB_MAX)
        accepted=wonder_fb_offer(&f->state,skb,fb_now());
    spin_unlock_irqrestore(&f->lock,flags);
    if (!accepted) fb_report(f,skb,WONDER_FB_FAILED);
}
static struct wonder_feedback *fb_context(struct wiphy *wiphy,struct wireless_dev *wdev)
{
    struct ieee80211_hw *hw=wiphy_to_ieee80211_hw(wiphy);
    struct wonder_data *wonder=hw->priv;
    if (!wonder_external_monitor || !wonder_external_tx || !wdev ||
        !wdev->netdev || wdev->wiphy!=wiphy || !netif_running(wdev->netdev)) return NULL;
    return wonder->feedback;
}
static int fb_request(const void *data,int length,u64 *owner,u64 *token,unsigned *outcome)
{
    const unsigned char *p=data;
    if (!capable(CAP_NET_ADMIN)) return -EPERM;
    if (!data || length!=WONDER_FB_HEADER || wonder_fb_word(p)!=WONDER_FB_VERSION ||
        wonder_fb_word(p+4) || wonder_fb_word(p+28)) return -EINVAL;
    *owner=fb_u64(p+8);*token=fb_u64(p+16);*outcome=wonder_fb_word(p+24);
    return *owner && *outcome<=WONDER_FB_ACKED?0:-EINVAL;
}
int wonder_feedback_pull(struct wiphy *wiphy,struct wireless_dev *wdev,const void *data,int length)
{
    struct wonder_feedback *f;struct wonder_fb_slot *slot;struct sk_buff *reply;
    unsigned char *payload;unsigned long flags;u64 owner,token;unsigned outcome,n=0;int ret;
    ret=fb_request(data,length,&owner,&token,&outcome);if (ret) return ret;
    if (token || outcome) return -EINVAL;
    f=fb_context(wiphy,wdev);if (!f) return -EOPNOTSUPP;
    payload=kzalloc(WONDER_FB_HEADER+WONDER_FB_MAX,GFP_KERNEL);if (!payload) return -ENOMEM;
    spin_lock_irqsave(&f->lock,flags);
    if (!wonder_fb_claim(&f->state,owner,fb_now())) {ret=-EBUSY;goto unlock;}
    slot=wonder_fb_take(&f->state);
    if (!slot) {ret=-ENODATA;goto unlock;}
    n=((struct sk_buff *)slot->packet)->len;token=slot->token;
    ret=skb_copy_bits(slot->packet,0,payload+WONDER_FB_HEADER,n);
    if (ret) goto unlock;
    slot->delivered=1;
    wonder_fb_put(payload,WONDER_FB_VERSION);wonder_fb_put(payload+4,n);
    fb_put64(payload+8,owner);fb_put64(payload+16,token);
unlock:
    spin_unlock_irqrestore(&f->lock,flags);
    if (ret) {kfree(payload);return ret;}
    reply=cfg80211_vendor_cmd_alloc_reply_skb(wiphy,WONDER_FB_HEADER+n);
    if (!reply) ret=-ENOMEM;
    else {skb_put_data(reply,payload,WONDER_FB_HEADER+n);ret=cfg80211_vendor_cmd_reply(reply);}
    kfree(payload);
    /* A lost reply is not redelivered: failure/ambiguous delivery waits for
     * timeout, preventing an automatic second transmission of the same skb. */
    return ret;
}
int wonder_feedback_complete(struct wiphy *wiphy,struct wireless_dev *wdev,const void *data,int length)
{
    struct wonder_feedback *f;struct sk_buff *skb;unsigned long flags;
    u64 owner,token;unsigned outcome;int ret=fb_request(data,length,&owner,&token,&outcome);
    if (ret) return ret;
    if (!token) return -EINVAL;
    f=fb_context(wiphy,wdev);if (!f) return -EOPNOTSUPP;
    spin_lock_irqsave(&f->lock,flags);
    skb=wonder_fb_finish(&f->state,owner,token);
    spin_unlock_irqrestore(&f->lock,flags);
    if (!skb) return -ENOENT;
    fb_report(f,skb,outcome);return 0;
}
int wonder_feedback_release(struct wiphy *wiphy,struct wireless_dev *wdev,const void *data,int length)
{
    struct wonder_feedback *f;unsigned long flags;u64 owner,token;unsigned outcome;
    void *packets[WONDER_FB_SLOTS];int i,n=0;
    int ret=fb_request(data,length,&owner,&token,&outcome);if (ret) return ret;
    if (token || outcome) return -EINVAL;
    f=fb_context(wiphy,wdev);if (!f) return -EOPNOTSUPP;
    spin_lock_irqsave(&f->lock,flags);
    if (f->state.owner!=owner) ret=-ENOENT;
    else {
        f->state.owner=0;
        n=wonder_fb_sweep(&f->state,fb_now(),packets);
    }
    spin_unlock_irqrestore(&f->lock,flags);
    for (i=0;i<n;i++) fb_report(f,packets[i],WONDER_FB_FAILED);
    return ret;
}
