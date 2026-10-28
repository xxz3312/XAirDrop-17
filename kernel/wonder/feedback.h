/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WONDER_FEEDBACK_H
#define WONDER_FEEDBACK_H
#include <net/mac80211.h>
struct wonder_data;
extern bool wonder_external_tx;
int wonder_feedback_init(struct wonder_data *wonder);
void wonder_feedback_shutdown(struct wonder_data *wonder);
void wonder_feedback_free(struct wonder_data *wonder);
void wonder_feedback_start(struct wonder_data *wonder);
void wonder_feedback_stop(struct wonder_data *wonder);
void wonder_feedback_tx(struct wonder_data *wonder,struct sk_buff *skb);
int wonder_feedback_pull(struct wiphy *,struct wireless_dev *,const void *,int);
int wonder_feedback_complete(struct wiphy *,struct wireless_dev *,const void *,int);
int wonder_feedback_release(struct wiphy *,struct wireless_dev *,const void *,int);
#endif
