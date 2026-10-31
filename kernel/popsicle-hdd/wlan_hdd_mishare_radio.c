// SPDX-License-Identifier: GPL-2.0-only
/* Owned NDI MLME lifecycle. No automatic runtime/HDD caller. */
#include <linux/errno.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <wlan_objmgr_vdev_obj.h>
#include <wlan_vdev_mlme_api.h>
#include <wlan_vdev_mlme.h>
#include <wlan_vdev_mgr_tgt_if_rx_defs.h>
#include <../../core/src/vdev_mgr_ops.h>
#include <scheduler_api.h>
#include <wmi_unified_param.h>
#include "wlan_hdd_mishare_events.h"
#include "wlan_hdd_mishare_ndi.h"
#include "wlan_hdd_mishare_radio.h"
#include "wlan_hdd_mishare_radio_mlme.h"

enum radio_work { RADIO_START, RADIO_STOP, RADIO_START_REPLY, RADIO_STOP_REPLY };
struct mishare_radio {
    struct mishare_radio *next;
    struct wlan_objmgr_vdev *vdev;
    struct mishare_event_owner *events; /* borrowed; runtime drains us first */
    void *owner;
    unsigned long session_cookie;
    u32 freq;
    struct mishare_radio_status state;
    bool preflight;
    bool start_reply_queued;
    bool stop_reply_queued;
    bool applying_start_reply;
    bool applying_stop_reply;
    bool start_posted;
    bool start_callback_entered;
    bool ssr_fenced_new;
    bool ssr_start_flushed;
    bool ssr_callback_after_fence;
    int start_post_error;
    bool ssr_fenced_rejected;
    bool ssr_start_refused;
    bool start_work_admitted;
    bool start_prepare_entered;
    bool ssr_fenced_before_prepare;
    bool ssr_start_aborted;
    bool start_prepare_succeeded;
    bool start_sm_committed;
    bool ssr_fenced_preparation;
    bool ssr_prepared_abort;
    struct mishare_ndi_start_summary start_plan;
    bool start_sm_entered;
    bool ssr_fenced_sm_gate;
    bool ssr_sm_entry_aborted;
    bool start_sm_call_active;
    bool start_sm_return_success;
    bool ssr_fenced_init;
    bool init_validate_rejected;
    bool init_down_rejected;
    bool init_native_notified;
    bool ssr_init_rejected;
};
struct radio_request {
    struct mishare_radio *radio;
    enum radio_work work;
    struct vdev_start_response start;
};
static DEFINE_SPINLOCK(mishare_radio_lock);
static struct mishare_radio *mishare_radios;

static bool radio_init_idle(struct mishare_radio *r)
{
    return wlan_vdev_mlme_get_state(r->vdev) == WLAN_VDEV_S_INIT &&
           wlan_vdev_mlme_get_substate(r->vdev) == WLAN_VDEV_SS_IDLE;
}

/* Radio lock held. No cleanup is inferred from INIT alone. */
static bool radio_init_reject_context(struct mishare_radio *r,
                                      unsigned int pending, unsigned int users)
{
    return r->ssr_fenced_init && r->start_sm_entered && r->start_sm_committed &&
           r->start_prepare_entered && r->start_prepare_succeeded && r->start_work_admitted &&
           r->start_callback_entered && r->start_posted && r->preflight &&
           !r->ssr_fenced_new && !r->ssr_fenced_before_prepare && !r->ssr_fenced_preparation &&
           !r->ssr_fenced_sm_gate && !r->ssr_start_flushed && !r->ssr_start_refused &&
           !r->ssr_start_aborted && !r->ssr_prepared_abort && !r->ssr_sm_entry_aborted &&
           !r->ssr_fenced_rejected && !r->start_post_error && !r->ssr_callback_after_fence &&
           r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
           r->state.error == -ESHUTDOWN && r->state.pending == pending && r->state.users == users &&
           !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
           !r->state.down_attempted && !r->state.down_accepted &&
           !r->start_reply_queued && !r->stop_reply_queued &&
           !r->applying_start_reply && !r->applying_stop_reply && radio_init_idle(r);
}

void mishare_radio_quiesce_psoc(struct wlan_objmgr_psoc *psoc)
{
    struct mishare_radio *r;
    unsigned long flags;
    if (!psoc)
        return;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (r = mishare_radios; r; r = r->next) {
        if (wlan_vdev_get_psoc(r->vdev) != psoc)
            continue;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_NEW &&
            !r->state.error && r->state.pending == 1 && !r->state.users &&
            r->start_posted && !r->start_callback_entered && !r->preflight &&
            !r->state.start_attempted && !r->state.stop_attempted &&
            !r->state.host_up && !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply)
            r->ssr_fenced_new = true;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_NEW &&
            !r->state.error && r->state.pending == 1 && !r->state.users &&
            r->start_posted && r->start_callback_entered && !r->start_prepare_entered &&
            !r->preflight && !r->state.start_attempted && !r->state.stop_attempted &&
            !r->state.host_up && !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply)
            r->ssr_fenced_before_prepare = true;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_NEW &&
            !r->state.error && r->state.pending == 1 && !r->state.users &&
            r->start_posted && r->start_callback_entered && r->start_work_admitted &&
            r->start_prepare_entered && !r->start_sm_committed && !r->preflight &&
            !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
            !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply)
            r->ssr_fenced_preparation = true;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_STARTING &&
            !r->state.error && r->state.pending == 1 && !r->state.users &&
            r->start_posted && r->start_callback_entered && r->start_work_admitted &&
            r->start_prepare_entered && r->start_prepare_succeeded &&
            r->start_sm_committed && !r->start_sm_entered && r->preflight &&
            !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
            !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply)
            r->ssr_fenced_sm_gate = true;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_STARTING &&
            !r->state.error && r->state.pending == 1 && !r->state.users &&
            r->start_posted && r->start_callback_entered && r->start_work_admitted &&
            r->start_prepare_entered && r->start_prepare_succeeded && r->start_sm_committed &&
            r->start_sm_entered && r->start_sm_call_active && r->preflight &&
            !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
            !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply && radio_init_idle(r))
            r->ssr_fenced_init = true;
        if (!r->state.closing && r->state.phase == MISHARE_RADIO_CANCELLED &&
            r->start_post_error && r->state.error == r->start_post_error &&
            !r->start_posted && !r->start_callback_entered && !r->preflight &&
            !r->state.pending && !r->state.users &&
            !r->state.start_attempted && !r->state.stop_attempted &&
            !r->state.host_up && !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply)
            r->ssr_fenced_rejected = true;
        r->state.closing = true;
        r->state.phase = MISHARE_RADIO_BLOCKED;
        if (!r->state.error)
            r->state.error = -ESHUTDOWN;
    }
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
}

static void radio_block(struct mishare_radio *r, int error)
{
    unsigned long flags;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.phase = MISHARE_RADIO_BLOCKED;
    if (!r->state.error)
        r->state.error = error ? error : -EUCLEAN;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
}

enum radio_callback_kind { RADIO_CB_OTHER, RADIO_CB_INIT_VALIDATE, RADIO_CB_INIT_DOWN };
static struct mishare_radio *radio_get_kind(struct vdev_mlme_obj *mlme,
                                            enum radio_callback_kind kind)
{
    struct mishare_radio *r;
    unsigned long flags;
    if (!mlme || !mlme->vdev)
        return NULL;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (r = mishare_radios; r; r = r->next) {
        if (r->vdev == mlme->vdev) {
            if (r->ssr_fenced_init) {
                bool expected = r->start_sm_call_active && radio_init_reject_context(r, 1, 0) &&
                    ((kind == RADIO_CB_INIT_VALIDATE && !r->init_validate_rejected &&
                      !r->init_down_rejected && !r->init_native_notified) ||
                     (kind == RADIO_CB_INIT_DOWN && r->init_validate_rejected &&
                      !r->init_down_rejected && !r->init_native_notified));
                if (!expected)
                    r->ssr_callback_after_fence = true;
            } else if (r->ssr_fenced_new || r->ssr_fenced_rejected ||
                r->ssr_fenced_before_prepare || r->ssr_fenced_preparation || r->ssr_fenced_sm_gate)
                r->ssr_callback_after_fence = true;
            r->state.users++;
            if (wlan_vdev_mlme_get_cmpt_obj(mlme->vdev) != mlme ||
                !mlme->ext_vdev_ptr ||
                wlan_vdev_mlme_get_opmode(mlme->vdev) != QDF_PASSTHRU_MODE ||
                mlme->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI ||
                mlme->mgmt.generic.subtype) {
                r->state.phase = MISHARE_RADIO_BLOCKED;
                r->state.error = -EUCLEAN;
            }
            break;
        }
    }
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    if (r && !mishare_runtime_work_allowed(r->vdev, r->owner))
        radio_block(r, -ESHUTDOWN);
    return r;
}
static struct mishare_radio *radio_get(struct vdev_mlme_obj *mlme)
{
    return radio_get_kind(mlme, RADIO_CB_OTHER);
}
static void radio_put(struct mishare_radio *r)
{
    unsigned long flags;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.users--;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
}
int mishare_radio_snapshot(struct mishare_radio *r, struct mishare_radio_status *s)
{
    unsigned long flags;
    if (!r || !s)
        return -EINVAL;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    *s = r->state;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return 0;
}

static bool radio_phase(struct mishare_radio *r, enum mishare_radio_phase phase)
{
    struct mishare_radio_status s;
    mishare_radio_snapshot(r, &s);
    return s.phase == phase;
}
static bool radio_applying(struct mishare_radio *r, bool start)
{
    unsigned long flags;
    bool applying;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    applying = start ? r->applying_start_reply : r->applying_stop_reply;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return applying;
}
static void radio_set_applying(struct mishare_radio *r, bool start, bool value)
{
    unsigned long flags;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (start)
        r->applying_start_reply = value;
    else
        r->applying_stop_reply = value;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
}
static QDF_STATUS radio_result(struct mishare_radio *r, int ret)
{
    if (ret)
        radio_block(r, ret);
    radio_put(r);
    return ret ? QDF_STATUS_E_FAILURE : QDF_STATUS_SUCCESS;
}
static int radio_sm(struct mishare_radio *r, enum wlan_vdev_sm_evt event, bool nested)
{
    QDF_STATUS status;
    unsigned long flags;
    bool allowed;
    int ret;

    if (!nested && event == WLAN_VDEV_SM_EV_START) {
        allowed = mishare_runtime_work_allowed(r->vdev, r->owner);
        spin_lock_irqsave(&mishare_radio_lock, flags);
        ret = !allowed || r->state.closing || r->state.phase != MISHARE_RADIO_STARTING ?
              -ESHUTDOWN : !r->start_sm_committed || r->start_sm_entered ||
              !r->start_prepare_succeeded || !r->preflight || r->state.users ? -EUCLEAN : 0;
        if (!ret) {
            r->start_sm_entered = true;
            r->start_sm_call_active = true;
        } else if (ret == -ESHUTDOWN && r->ssr_fenced_sm_gate &&
                   r->start_sm_committed && !r->start_sm_entered &&
                   r->start_prepare_succeeded && r->start_prepare_entered &&
                   r->start_work_admitted && r->start_callback_entered && r->start_posted &&
                   !r->ssr_fenced_new && !r->ssr_fenced_before_prepare && !r->ssr_fenced_preparation &&
                   !r->ssr_start_flushed && !r->ssr_start_refused && !r->ssr_start_aborted &&
                   !r->ssr_prepared_abort && !r->ssr_fenced_rejected && !r->start_post_error &&
                   !r->ssr_callback_after_fence && r->state.phase == MISHARE_RADIO_BLOCKED &&
                   r->state.closing && r->state.error == -ESHUTDOWN &&
                   r->state.pending == 1 && !r->state.users && r->preflight &&
                   !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
                   !r->state.down_attempted && !r->state.down_accepted &&
                   !r->start_reply_queued && !r->stop_reply_queued &&
                   !r->applying_start_reply && !r->applying_stop_reply) {
            r->ssr_sm_entry_aborted = true;
            r->state.ssr_start_sm_entry_aborted = true;
        }
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        if (ret)
            return ret;
    }
    /* MLME callbacks already hold the native SM lock. Never reacquire it. */
    if (nested)
        status = wlan_vdev_mlme_sm_deliver_evt_sync(r->vdev, event, 0, NULL);
    else
        status = wlan_vdev_mlme_sm_deliver_evt(r->vdev, event, 0, NULL);
    if (!nested && event == WLAN_VDEV_SM_EV_START) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->start_sm_call_active = false;
        r->start_sm_return_success = !QDF_IS_STATUS_ERROR(status);
        ret = QDF_IS_STATUS_ERROR(status) ? -EUCLEAN : 0;
        if (!ret && radio_init_reject_context(r, 1, 0) &&
            r->init_validate_rejected && r->init_down_rejected && r->init_native_notified) {
            r->ssr_init_rejected = true;
            r->state.ssr_start_init_rejected = true;
            ret = -ESHUTDOWN;
        }
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return ret;
    }
    return QDF_IS_STATUS_ERROR(status) ? -EUCLEAN : 0;
}
static QDF_STATUS radio_finish(struct scheduler_msg *msg, bool flushed);
static QDF_STATUS radio_callback(struct scheduler_msg *msg)
{
    return radio_finish(msg, false);
}
static QDF_STATUS radio_flush(struct scheduler_msg *msg)
{
    return radio_finish(msg, true);
}
static int radio_post(struct mishare_radio *r, enum radio_work work,
                       const struct vdev_start_response *start)
{
    struct radio_request *req;
    struct scheduler_msg msg = {0};
    QDF_STATUS status;
    unsigned long flags;
    int ret;
    req = kzalloc(sizeof(*req), GFP_ATOMIC);
    if (!req)
        return -ENOMEM;
    req->radio = r;
    req->work = work;
    if (start)
        req->start = *start;
    msg.bodyptr = req;
    msg.callback = radio_callback;
    msg.flush_callback = radio_flush;
    ret = mishare_runtime_work_get(r->vdev, r->owner);
    if (ret) {
        kfree(req);
        return ret;
    }
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.pending++;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    status = scheduler_post_message(QDF_MODULE_ID_HDD, QDF_MODULE_ID_PE,
                                    QDF_MODULE_ID_TARGET_IF, &msg);
    if (QDF_IS_STATUS_ERROR(status)) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->state.pending--;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        mishare_runtime_work_put(r->vdev, r->owner);
        kfree(req);
        /* Native scheduler errors precede insertion. Record only after
         * returning the work reservation and freeing our request. */
        if (work == RADIO_START) {
            spin_lock_irqsave(&mishare_radio_lock, flags);
            r->start_post_error = qdf_status_to_os_return(status);
            spin_unlock_irqrestore(&mishare_radio_lock, flags);
        }
        return qdf_status_to_os_return(status);
    }
    return 0;
}

QDF_STATUS mishare_radio_validate(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get_kind(m, RADIO_CB_INIT_VALIDATE);
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    {
        unsigned long flags;
        spin_lock_irqsave(&mishare_radio_lock, flags);
        ret = r->state.phase != MISHARE_RADIO_STARTING || !r->preflight ||
              !r->start_sm_committed || !r->start_sm_entered ||
              !radio_init_idle(r) ? -EUCLEAN : 0;
        if (ret && r->start_sm_call_active && radio_init_reject_context(r, 1, 1) &&
            !r->init_validate_rejected && !r->init_down_rejected && !r->init_native_notified)
            r->init_validate_rejected = true;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    return radio_result(r, ret);
}

static QDF_STATUS radio_send(struct vdev_mlme_obj *m, bool start)
{
    struct mishare_radio *r = radio_get(m);
    enum mishare_radio_phase phase = start ? MISHARE_RADIO_STARTING : MISHARE_RADIO_STOPPING;
    QDF_STATUS status;
    u64 ticket;
    unsigned long flags;
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    if (!radio_phase(r, phase) ||
        wlan_vdev_mlme_get_state(r->vdev) != (start ? WLAN_VDEV_S_START : WLAN_VDEV_S_STOP) ||
        wlan_vdev_mlme_get_substate(r->vdev) !=
            (start ? WLAN_VDEV_SS_START_START_PROGRESS : WLAN_VDEV_SS_STOP_STOP_PROGRESS) ||
        !m->ext_vdev_ptr || m->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI ||
        m->mgmt.generic.subtype || wlan_vdev_mlme_get_opmode(r->vdev) != QDF_PASSTHRU_MODE)
        return radio_result(r, -EUCLEAN);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    ret = start ? r->state.start_attempted : r->state.stop_attempted;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    if (ret)
        return radio_result(r, -EALREADY);
    ret = mishare_events_begin_vdev(r->events, r->vdev,
                                   start ? MISHARE_TXN_START : MISHARE_TXN_STOP, &ticket);
    if (ret)
        return radio_result(r, ret);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (start)
        r->state.start_attempted = true;
    else
        r->state.stop_attempted = true;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    status = start ? vdev_mgr_start_send(m, false) : vdev_mgr_stop_send(m);
    ret = mishare_events_submitted(r->events, ticket,
                                  QDF_IS_STATUS_ERROR(status) ? MISHARE_TXN_UNKNOWN : MISHARE_TXN_ACCEPTED);
    if (QDF_IS_STATUS_ERROR(status) || ret)
        return radio_result(r, -EUCLEAN);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (r->state.phase == phase)
        r->state.phase = start ? MISHARE_RADIO_WAIT_START : MISHARE_RADIO_WAIT_STOP;
    else
        ret = -EUCLEAN;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_start_send(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    return radio_send(m, true);
}
QDF_STATUS mishare_radio_stop_send(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    return radio_send(m, false);
}
QDF_STATUS mishare_radio_start_continue(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    ret = !radio_phase(r, MISHARE_RADIO_WAIT_START) || !radio_applying(r, true) ?
          -EUCLEAN : radio_sm(r, WLAN_VDEV_SM_EV_START_SUCCESS, true);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_beacon(struct vdev_mlme_obj *m, enum beacon_update_op op,
                                uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    /* NDI host-only UP has no beacon command. Admit only the owned INIT event. */
    return radio_result(r, !radio_phase(r, MISHARE_RADIO_WAIT_START) ||
                           !radio_applying(r, true) || op != BEACON_INIT ? -EUCLEAN : 0);
}
QDF_STATUS mishare_radio_up_send(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    unsigned long flags;
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    if (!radio_phase(r, MISHARE_RADIO_WAIT_START) || !radio_applying(r, true))
        return radio_result(r, -EUCLEAN);
    ret = mishare_ndi_radio_host_up(r->vdev);
    if (!ret) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->state.host_up = true;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_up_complete(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    unsigned long flags;
    int ret = 0;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (r->state.phase != MISHARE_RADIO_WAIT_START || !r->state.host_up ||
        !r->applying_start_reply)
        ret = -EUCLEAN;
    else
        r->state.phase = MISHARE_RADIO_UP;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_disconnect(struct vdev_mlme_obj *m, uint16_t len,
                                    void *data, bool legacy_only)
{
    struct mishare_radio *r = radio_get(m);
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    /* Keep the firmware self-peer until real STOP and accepted DOWN. */
    ret = !radio_phase(r, MISHARE_RADIO_STOPPING) || legacy_only ? -EUCLEAN :
          radio_sm(r, WLAN_VDEV_SM_EV_DISCONNECT_COMPLETE, true);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_stop_continue(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    ret = !radio_phase(r, MISHARE_RADIO_WAIT_STOP) || !radio_applying(r, false) ?
          -EUCLEAN : radio_sm(r, WLAN_VDEV_SM_EV_MLME_DOWN_REQ, true);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_down_send(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get(m);
    QDF_STATUS status;
    unsigned long flags;
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    {
        struct mishare_radio_status s;
        mishare_radio_snapshot(r, &s);
        ret = s.down_attempted;
    }
    if (!radio_phase(r, MISHARE_RADIO_WAIT_STOP) || !radio_applying(r, false) || ret)
        return radio_result(r, -EUCLEAN);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.down_attempted = true;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    status = vdev_mgr_down_send(m); /* Native target-if releases STOP PM locks. */
    if (QDF_IS_STATUS_ERROR(status))
        return radio_result(r, -EUCLEAN);
    ret = mishare_ndi_radio_mark_down(r->vdev);
    if (ret)
        return radio_result(r, ret);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.down_accepted = true;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return radio_result(r, radio_sm(r, WLAN_VDEV_SM_EV_DOWN_COMPLETE, true));
}
QDF_STATUS mishare_radio_down_complete(struct vdev_mlme_obj *m, uint16_t len, void *data)
{
    struct mishare_radio *r = radio_get_kind(m, RADIO_CB_INIT_DOWN);
    unsigned long flags;
    int ret = 0;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (r->state.phase != MISHARE_RADIO_WAIT_STOP || !r->state.down_accepted ||
        !r->applying_stop_reply || wlan_vdev_mlme_get_state(r->vdev) != WLAN_VDEV_S_INIT)
        ret = -EUCLEAN;
    else
        r->state.phase = MISHARE_RADIO_DOWN;
    if (ret && r->start_sm_call_active && radio_init_reject_context(r, 1, 1) &&
        r->init_validate_rejected && !r->init_down_rejected && !r->init_native_notified)
        r->init_down_rejected = true;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return radio_result(r, ret);
}

/* Native INIT failure provenance only; no state transition or cleanup. */
void mishare_radio_native_init_rejected(struct vdev_mlme_obj *m)
{
    struct mishare_radio *r;
    unsigned long flags;

    if (!m || !m->vdev)
        return;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (r = mishare_radios; r && r->vdev != m->vdev; r = r->next)
        ;
    if (r && r->ssr_fenced_init) {
        if (wlan_vdev_mlme_get_cmpt_obj(m->vdev) == m && m->ext_vdev_ptr &&
            wlan_vdev_mlme_get_opmode(m->vdev) == QDF_PASSTHRU_MODE &&
            m->mgmt.generic.type == WLAN_VDEV_MLME_TYPE_NDI && !m->mgmt.generic.subtype &&
            r->start_sm_call_active && radio_init_reject_context(r, 1, 0) &&
            r->init_validate_rejected && r->init_down_rejected && !r->init_native_notified)
            r->init_native_notified = true;
        else
            r->ssr_callback_after_fence = true;
    }
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
}

static QDF_STATUS radio_reply(struct vdev_mlme_obj *m, bool start,
                              const struct vdev_start_response *rsp, u8 id)
{
    struct mishare_radio *r = radio_get(m);
    struct mishare_vdev_txn txn;
    unsigned long flags;
    bool duplicate;
    int ret;
    if (!r)
        return QDF_STATUS_E_NOSUPPORT;
    ret = mishare_events_snapshot(r->events, &txn);
    if (ret || id != wlan_vdev_get_id(r->vdev) ||
        (start && (!rsp || rsp->resp_type != WMI_HOST_VDEV_START_RESP_EVENT || rsp->status)) ||
        txn.state == MISHARE_TXN_QUARANTINED ||
        !((txn.state == (start ? MISHARE_TXN_STARTED : MISHARE_TXN_STOPPED) &&
           txn.pending == MISHARE_TXN_NONE) ||
          (txn.pending == (start ? MISHARE_TXN_START : MISHARE_TXN_STOP) && txn.replied)))
        return radio_result(r, -EUCLEAN);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    duplicate = start ? r->start_reply_queued : r->stop_reply_queued;
    if (start)
        r->start_reply_queued = true;
    else
        r->stop_reply_queued = true;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    if (duplicate)
        return radio_result(r, -EALREADY);
    ret = radio_post(r, start ? RADIO_START_REPLY : RADIO_STOP_REPLY, rsp);
    return radio_result(r, ret);
}
QDF_STATUS mishare_radio_start_rsp(struct vdev_mlme_obj *m, struct vdev_start_response *rsp)
{
    if (!rsp) {
        struct mishare_radio *r = radio_get(m);
        return r ? radio_result(r, -EINVAL) : QDF_STATUS_E_NOSUPPORT;
    }
    return radio_reply(m, true, rsp, rsp->vdev_id);
}
QDF_STATUS mishare_radio_stop_rsp(struct vdev_mlme_obj *m, struct vdev_stop_response *rsp)
{
    if (!rsp) {
        struct mishare_radio *r = radio_get(m);
        return r ? radio_result(r, -EINVAL) : QDF_STATUS_E_NOSUPPORT;
    }
    return radio_reply(m, false, NULL, rsp->vdev_id);
}

/* Called only at exits before START preparation. The fence and prepare-entry
 * flag share the radio lock; an error returned by preparation is never proof. */
static int radio_abort_before_prepare(struct radio_request *req)
{
    struct mishare_radio *r = req->radio;
    unsigned long flags;

    spin_lock_irqsave(&mishare_radio_lock, flags);
    if (req->work == RADIO_START && r->ssr_fenced_before_prepare &&
        r->start_work_admitted && !r->start_prepare_entered &&
        r->start_posted && r->start_callback_entered &&
        !r->ssr_fenced_new && !r->ssr_start_flushed && !r->ssr_start_refused &&
        !r->ssr_fenced_rejected && !r->start_post_error && !r->ssr_callback_after_fence &&
        !r->preflight && r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
        r->state.error == -ESHUTDOWN && r->state.pending == 1 && !r->state.users &&
        !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
        !r->state.down_attempted && !r->state.down_accepted &&
        !r->start_reply_queued && !r->stop_reply_queued &&
        !r->applying_start_reply && !r->applying_stop_reply) {
        r->ssr_start_aborted = true;
        r->state.ssr_start_body_aborted = true;
    }
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    return -ESHUTDOWN;
}

static bool radio_plan_equal(const struct mishare_ndi_start_summary *a,
                              const struct mishare_ndi_start_summary *b)
{
    return a->freq == b->freq && a->center_freq == b->center_freq &&
           a->phy_mode == b->phy_mode && a->tx_streams == b->tx_streams &&
           a->rx_streams == b->rx_streams && a->beacon_interval == b->beacon_interval &&
           a->dtim_period == b->dtim_period;
}

static int radio_execute(struct radio_request *req)
{
    struct mishare_radio *r = req->radio;
    struct mishare_vdev_txn txn;
    struct vdev_mlme_obj *m;
    struct mishare_radio_status s;
    struct mishare_ndi_start_summary prepared_plan = {0};
    unsigned long flags;
    int ret;
    if (!mishare_runtime_work_allowed(r->vdev, r->owner))
        return radio_abort_before_prepare(req);
    m = wlan_vdev_mlme_get_cmpt_obj(r->vdev);
    mishare_radio_snapshot(r, &s);
    if (m && s.phase == MISHARE_RADIO_BLOCKED && req->work == RADIO_START)
        return radio_abort_before_prepare(req);
    if (!m || s.phase == MISHARE_RADIO_BLOCKED)
        return -EUCLEAN;
    switch (req->work) {
    case RADIO_START:
        if (s.phase != MISHARE_RADIO_NEW)
            return -EUCLEAN;
        if (s.closing) {
            spin_lock_irqsave(&mishare_radio_lock, flags);
            ret = r->state.phase == MISHARE_RADIO_NEW ? 0 : -ESHUTDOWN;
            if (!ret)
                r->state.phase = MISHARE_RADIO_CANCELLED;
            spin_unlock_irqrestore(&mishare_radio_lock, flags);
            return ret;
        }
        spin_lock_irqsave(&mishare_radio_lock, flags);
        ret = r->state.phase != MISHARE_RADIO_NEW || r->state.closing ? -ESHUTDOWN :
              r->start_prepare_entered ? -EUCLEAN : 0;
        if (!ret)
            r->start_prepare_entered = true;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        if (ret)
            return ret == -ESHUTDOWN ? radio_abort_before_prepare(req) : ret;
        ret = mishare_ndi_radio_prepare(r->vdev, r->owner, r->session_cookie, r->freq);
        if (ret) {
            /* Preparation can partially change host fields. Quarantine rather
             * than manufacture an INIT/DOWN or assume safe rollback. */
            return ret;
        }
        /* Rebuild only the native encoder summary, never a WMI command. A
         * successful preparation may not silently change the completed plan. */
        ret = mishare_ndi_start_plan_build(m, r->freq, &prepared_plan);
        if (ret || !radio_plan_equal(&prepared_plan, &r->start_plan))
            return -EUCLEAN;
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->start_prepare_succeeded = true;
        ret = r->state.phase != MISHARE_RADIO_NEW || r->state.closing ? -ESHUTDOWN : 0;
        if (!ret) {
            r->preflight = true;
            r->start_sm_committed = true;
            r->state.phase = MISHARE_RADIO_STARTING;
        } else if (r->ssr_fenced_preparation && !r->start_sm_committed &&
                   !r->ssr_fenced_new && !r->ssr_fenced_before_prepare &&
                   !r->ssr_start_flushed && !r->ssr_start_refused && !r->ssr_start_aborted &&
                   !r->ssr_fenced_rejected && !r->start_post_error && !r->ssr_callback_after_fence &&
                   r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
                   r->state.error == -ESHUTDOWN && r->state.pending == 1 && !r->state.users &&
                   !r->preflight && !r->state.start_attempted && !r->state.stop_attempted &&
                   !r->state.host_up && !r->state.down_attempted && !r->state.down_accepted &&
                   !r->start_reply_queued && !r->stop_reply_queued &&
                   !r->applying_start_reply && !r->applying_stop_reply) {
            r->ssr_prepared_abort = true;
            r->state.ssr_start_prepared_aborted = true;
        }
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        if (ret)
            return ret; /* Preparation ran: never publish pre-prepare abort. */
        ret = radio_sm(r, WLAN_VDEV_SM_EV_START, false);
        if (ret)
            return ret;
        return radio_phase(r, MISHARE_RADIO_WAIT_START) ? 0 : -EUCLEAN;
    case RADIO_STOP:
        if (s.phase != MISHARE_RADIO_STOPPING || !s.closing || !s.host_up ||
            wlan_vdev_mlme_get_state(r->vdev) != WLAN_VDEV_S_UP)
            return -EUCLEAN;
        ret = radio_sm(r, WLAN_VDEV_SM_EV_DOWN, false);
        return ret || !radio_phase(r, MISHARE_RADIO_WAIT_STOP) ? -EUCLEAN : 0;
    case RADIO_START_REPLY:
        if (s.phase != MISHARE_RADIO_WAIT_START || mishare_events_snapshot(r->events, &txn) ||
            txn.state != MISHARE_TXN_STARTED || txn.pending != MISHARE_TXN_NONE)
            return -EUCLEAN;
        radio_set_applying(r, true, true);
        ret = mishare_ndi_radio_start_response(m, &req->start);
        radio_set_applying(r, true, false);
        if (ret || !radio_phase(r, MISHARE_RADIO_UP))
            return -EUCLEAN;
        return 0;
    case RADIO_STOP_REPLY:
        if (s.phase != MISHARE_RADIO_WAIT_STOP || mishare_events_snapshot(r->events, &txn) ||
            txn.state != MISHARE_TXN_STOPPED || txn.pending != MISHARE_TXN_NONE)
            return -EUCLEAN;
        radio_set_applying(r, false, true);
        ret = radio_sm(r, WLAN_VDEV_SM_EV_STOP_RESP, false);
        radio_set_applying(r, false, false);
        return ret || !radio_phase(r, MISHARE_RADIO_DOWN) ? -EUCLEAN : 0;
    }
    return -EINVAL;
}
static QDF_STATUS radio_finish(struct scheduler_msg *msg, bool flushed)
{
    struct radio_request *req = msg->bodyptr;
    struct mishare_radio *r;
    struct wlan_objmgr_vdev *vdev;
    struct wlan_objmgr_psoc *psoc;
    void *owner, *token;
    bool publish_flush = false, publish_refused = false, publish_aborted = false;
    bool publish_prepared = false;
    bool publish_sm_entry = false;
    bool publish_init_rejected = false;
    unsigned long flags;
    int ret;
    if (!req)
        return QDF_STATUS_E_INVAL;
    r = req->radio;
    vdev = r->vdev;
    psoc = wlan_vdev_get_psoc(vdev);
    owner = r->owner;
    token = r;
    if (!flushed && req->work == RADIO_START) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->start_callback_entered = true;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    if (flushed && req->work == RADIO_START) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        if (r->ssr_fenced_new && !r->ssr_start_flushed &&
            !r->start_callback_entered && !r->ssr_callback_after_fence &&
            r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
            r->state.error == -ESHUTDOWN && r->state.pending == 1 && !r->state.users &&
            !r->preflight && !r->state.start_attempted && !r->state.stop_attempted &&
            !r->state.host_up && !r->state.down_attempted && !r->state.down_accepted &&
            !r->start_reply_queued && !r->stop_reply_queued &&
            !r->applying_start_reply && !r->applying_stop_reply) {
            r->ssr_start_flushed = true;
            publish_flush = true;
        }
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    if (flushed && req->work == RADIO_START && radio_phase(r, MISHARE_RADIO_NEW)) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        ret = r->state.phase == MISHARE_RADIO_NEW ? 0 : -ESHUTDOWN;
        if (!ret) {
            r->state.phase = MISHARE_RADIO_CANCELLED;
            r->state.error = -ECANCELED;
        }
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    } else {
        ret = flushed ? -ECANCELED : mishare_runtime_work_enter(r->vdev, r->owner);
        if (!ret) {
            if (req->work == RADIO_START) {
                spin_lock_irqsave(&mishare_radio_lock, flags);
                r->start_work_admitted = true;
                spin_unlock_irqrestore(&mishare_radio_lock, flags);
            }
            ret = radio_execute(req);
            mishare_runtime_work_exit(r->vdev, r->owner);
            if (req->work == RADIO_START && ret == -ESHUTDOWN) {
                spin_lock_irqsave(&mishare_radio_lock, flags);
                publish_aborted = r->ssr_start_aborted;
                publish_prepared = r->ssr_prepared_abort;
                publish_sm_entry = r->ssr_sm_entry_aborted;
                publish_init_rejected = r->ssr_init_rejected;
                spin_unlock_irqrestore(&mishare_radio_lock, flags);
            }
        } else if (!flushed && req->work == RADIO_START && ret == -ESHUTDOWN) {
            spin_lock_irqsave(&mishare_radio_lock, flags);
            if (r->ssr_fenced_new && r->start_posted && r->start_callback_entered &&
                !r->ssr_start_flushed && !r->ssr_start_refused &&
                !r->ssr_fenced_rejected && !r->start_post_error &&
                !r->ssr_callback_after_fence && !r->preflight &&
                r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
                r->state.error == -ESHUTDOWN && r->state.pending == 1 && !r->state.users &&
                !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
                !r->state.down_attempted && !r->state.down_accepted &&
                !r->start_reply_queued && !r->stop_reply_queued &&
                !r->applying_start_reply && !r->applying_stop_reply) {
                r->ssr_start_refused = true;
                r->state.ssr_start_callback_refused = true;
                publish_refused = true;
            }
            spin_unlock_irqrestore(&mishare_radio_lock, flags);
        }
    }
    if (ret)
        radio_block(r, ret);
    kfree(req);
    msg->bodyptr = NULL;
    mishare_runtime_work_put(r->vdev, r->owner);
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.pending--;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    /* No access to r after the last pending reference is released. */
    if (publish_flush)
        mishare_runtime_radio_start_flushed(psoc, vdev, owner, token);
    else if (publish_refused)
        mishare_runtime_radio_start_refused(psoc, vdev, owner, token);
    else if (publish_aborted)
        mishare_runtime_radio_start_aborted(psoc, vdev, owner, token);
    else if (publish_prepared)
        mishare_runtime_radio_prepared_aborted(psoc, vdev, owner, token);
    else if (publish_sm_entry)
        mishare_runtime_radio_sm_entry_aborted(psoc, vdev, owner, token);
    else if (publish_init_rejected)
        mishare_runtime_radio_init_rejected(psoc, vdev, owner, token);
    return QDF_STATUS_SUCCESS;
}

int mishare_radio_open(struct wlan_objmgr_vdev *vdev,
                       struct mishare_event_owner *events, void *owner,
                       unsigned long cookie, u32 freq,
                       const struct mishare_ndi_start_summary *plan, struct mishare_radio **out)
{
    struct mishare_radio *r, *other;
    struct vdev_mlme_obj *m;
    unsigned long flags;
    int ret;
    if (!vdev || !events || !owner || !cookie || !freq || !plan || !out || *out ||
        plan->freq != freq || plan->center_freq != freq || !plan->phy_mode ||
        !plan->tx_streams || plan->tx_streams > 2 || plan->rx_streams != plan->tx_streams)
        return -EINVAL;
    if (!mishare_runtime_work_allowed(vdev, owner))
        return -ESHUTDOWN;
    m = wlan_vdev_mlme_get_cmpt_obj(vdev);
    if (!m || m->vdev != vdev || !m->ext_vdev_ptr ||
        wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE ||
        m->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI ||
        m->mgmt.generic.subtype || wlan_vdev_mlme_get_state(vdev) != WLAN_VDEV_S_INIT)
        return -EINVAL;
    r = kzalloc(sizeof(*r), GFP_KERNEL);
    if (!r)
        return -ENOMEM;
    if (wlan_objmgr_vdev_try_get_ref(vdev, WLAN_HDD_ID_OBJ_MGR) != QDF_STATUS_SUCCESS) {
        kfree(r);
        return -ENODEV;
    }
    r->vdev = vdev;
    r->events = events;
    r->owner = owner;
    r->session_cookie = cookie;
    r->freq = freq;
    r->start_plan = *plan;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (other = mishare_radios; other; other = other->next) {
        if (other->vdev == vdev) {
            spin_unlock_irqrestore(&mishare_radio_lock, flags);
            wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
            kfree(r);
            return -EEXIST;
        }
    }
    r->next = mishare_radios;
    mishare_radios = r;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    *out = r;
    ret = radio_post(r, RADIO_START, NULL);
    if (!ret) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        r->start_posted = true;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    if (ret) {
        spin_lock_irqsave(&mishare_radio_lock, flags);
        if (r->state.phase == MISHARE_RADIO_NEW) {
            r->state.phase = ret == -ESHUTDOWN || ret == -EOVERFLOW ?
                             MISHARE_RADIO_BLOCKED : MISHARE_RADIO_CANCELLED;
            r->state.closing = r->state.phase == MISHARE_RADIO_BLOCKED;
        }
        if (!r->state.error)
            r->state.error = ret;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
    }
    return ret ? ret : -EINPROGRESS;
}

/* Radio registry lock held. This is provenance, not a synthesized DOWN. */
static bool radio_ssr_cancel_shape(struct mishare_radio *r)
{
    return (((!r->ssr_init_rejected && !r->state.ssr_start_init_rejected) &&
             (((!r->ssr_sm_entry_aborted && !r->state.ssr_start_sm_entry_aborted) &&
             (((!r->ssr_prepared_abort && !r->state.ssr_start_prepared_aborted &&
              !r->start_prepare_succeeded) &&
             ((r->ssr_fenced_new && r->ssr_start_flushed && r->start_posted &&
             !r->ssr_fenced_rejected && !r->start_post_error &&
             !r->ssr_start_refused && !r->start_callback_entered &&
             !r->state.ssr_start_callback_refused && !r->ssr_start_aborted &&
             r->state.error == -ESHUTDOWN) ||
            (r->ssr_fenced_rejected && r->start_post_error &&
             !r->ssr_fenced_new && !r->ssr_start_flushed && !r->start_posted &&
             !r->ssr_start_refused && !r->start_callback_entered &&
             !r->state.ssr_start_callback_refused && !r->ssr_start_aborted &&
             r->state.error == r->start_post_error) ||
            (r->ssr_fenced_new && r->ssr_start_refused && r->start_posted &&
             r->start_callback_entered && r->state.ssr_start_callback_refused &&
             !r->ssr_start_flushed && !r->ssr_fenced_rejected && !r->start_post_error &&
             !r->ssr_start_aborted && r->state.error == -ESHUTDOWN) ||
            (r->ssr_fenced_before_prepare && r->ssr_start_aborted &&
             r->state.ssr_start_body_aborted && r->start_posted && r->start_callback_entered &&
             !r->ssr_fenced_new && !r->ssr_start_flushed && !r->ssr_start_refused &&
             !r->state.ssr_start_callback_refused && !r->ssr_fenced_rejected && !r->start_post_error &&
             r->state.error == -ESHUTDOWN))) ||
            (r->ssr_fenced_preparation && r->ssr_prepared_abort &&
             r->start_prepare_succeeded && r->state.ssr_start_prepared_aborted &&
             !r->ssr_fenced_new && !r->ssr_fenced_before_prepare &&
             !r->ssr_start_flushed && !r->ssr_start_refused && !r->ssr_start_aborted &&
             !r->state.ssr_start_callback_refused && !r->state.ssr_start_body_aborted &&
             !r->ssr_fenced_rejected && !r->start_post_error &&
             r->start_posted && r->start_callback_entered && r->state.error == -ESHUTDOWN))) ||
            (r->ssr_fenced_sm_gate && r->ssr_sm_entry_aborted &&
             r->state.ssr_start_sm_entry_aborted && r->start_prepare_succeeded &&
             r->start_posted && r->start_callback_entered &&
             !r->ssr_fenced_new && !r->ssr_fenced_before_prepare && !r->ssr_fenced_preparation &&
             !r->ssr_start_flushed && !r->ssr_start_refused && !r->ssr_start_aborted &&
             !r->ssr_prepared_abort && !r->ssr_fenced_rejected && !r->start_post_error &&
             !r->state.ssr_start_callback_refused && !r->state.ssr_start_body_aborted &&
             !r->state.ssr_start_prepared_aborted && r->state.error == -ESHUTDOWN))) ||
            (r->ssr_init_rejected && r->state.ssr_start_init_rejected &&
             r->init_native_notified && r->init_validate_rejected && r->init_down_rejected &&
             r->start_sm_return_success && radio_init_reject_context(r, 0, 0))) &&
           r->start_work_admitted == (r->state.ssr_start_body_aborted || r->state.ssr_start_prepared_aborted || r->state.ssr_start_sm_entry_aborted || r->state.ssr_start_init_rejected) &&
           r->ssr_fenced_before_prepare == r->state.ssr_start_body_aborted &&
           r->start_prepare_entered == (r->state.ssr_start_prepared_aborted || r->state.ssr_start_sm_entry_aborted || r->state.ssr_start_init_rejected) &&
           r->ssr_fenced_preparation == r->state.ssr_start_prepared_aborted &&
           r->start_sm_committed == (r->state.ssr_start_sm_entry_aborted || r->state.ssr_start_init_rejected) &&
           r->ssr_fenced_sm_gate == r->state.ssr_start_sm_entry_aborted &&
           r->start_sm_entered == r->state.ssr_start_init_rejected &&
           r->ssr_fenced_init == r->state.ssr_start_init_rejected && !r->start_sm_call_active &&
           !r->ssr_callback_after_fence && r->preflight == (r->state.ssr_start_sm_entry_aborted || r->state.ssr_start_init_rejected) &&
           r->state.phase == MISHARE_RADIO_BLOCKED && r->state.closing &&
           !r->state.pending && !r->state.users &&
           !r->state.ssr_cancelled_before_start &&
           !r->state.start_attempted && !r->state.stop_attempted && !r->state.host_up &&
           !r->state.down_attempted && !r->state.down_accepted &&
           !r->start_reply_queued && !r->stop_reply_queued &&
           !r->applying_start_reply && !r->applying_stop_reply;
}

int mishare_radio_ssr_cancel_check(struct mishare_radio *token,
                                   struct wlan_objmgr_vdev *vdev,
                                   struct mishare_event_owner *events, void *owner,
                                   unsigned long cookie, u32 freq)
{
    struct mishare_radio *r;
    struct vdev_mlme_obj *m;
    struct mishare_vdev_txn txn;
    struct mishare_ndi_start_summary expected_plan = {0}, observed_plan = {0};
    bool prepared = false;
    unsigned long flags;
    int ret = -ENOENT;
    if (!token || !vdev || !events || !owner || !cookie || !freq)
        return -EINVAL;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (r = mishare_radios; r && r != token; r = r->next)
        ;
    if (r) {
        ret = r->vdev != vdev || r->events != events || r->owner != owner ||
              r->session_cookie != cookie || r->freq != freq ||
              !radio_ssr_cancel_shape(r) ? -EUCLEAN : 0;
        if (!ret) {
            prepared = r->state.ssr_start_prepared_aborted || r->state.ssr_start_sm_entry_aborted || r->state.ssr_start_init_rejected;
            expected_plan = r->start_plan;
        }
    }
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    if (ret)
        return ret;
    m = wlan_vdev_mlme_get_cmpt_obj(vdev);
    if (!m || m->vdev != vdev || !m->ext_vdev_ptr ||
        wlan_vdev_mlme_get_opmode(vdev) != QDF_PASSTHRU_MODE ||
        m->mgmt.generic.type != WLAN_VDEV_MLME_TYPE_NDI || m->mgmt.generic.subtype ||
        wlan_vdev_mlme_get_state(vdev) != WLAN_VDEV_S_INIT ||
        mishare_events_snapshot(events, &txn) || txn.state != MISHARE_TXN_QUARANTINED ||
        txn.serial || txn.pending != MISHARE_TXN_NONE || txn.submitted || txn.replied)
        return -EUCLEAN;
    /* Never hold the radio lock while entering the native encoder. */
    if (prepared && (mishare_ndi_start_plan_build(m, freq, &observed_plan) ||
                     !radio_plan_equal(&observed_plan, &expected_plan)))
        return -EUCLEAN;
    return 0;
}

int mishare_radio_ssr_cancel_release(struct mishare_radio **handle,
                                     struct wlan_objmgr_vdev *vdev,
                                     struct mishare_event_owner *events, void *owner,
                                     unsigned long cookie, u32 freq,
                                     struct mishare_radio_status *last)
{
    struct mishare_radio *r, **link;
    unsigned long flags;
    int ret;
    if (!handle || !last)
        return -EINVAL;
    r = *handle;
    ret = mishare_radio_ssr_cancel_check(r, vdev, events, owner, cookie, freq);
    if (ret)
        return ret;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    for (link = &mishare_radios; *link && *link != r; link = &(*link)->next)
        ;
    if (!*link || r->vdev != vdev || r->events != events || r->owner != owner ||
        r->session_cookie != cookie || r->freq != freq || !radio_ssr_cancel_shape(r) ||
        wlan_vdev_mlme_get_state(vdev) != WLAN_VDEV_S_INIT) {
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EUCLEAN;
    }
    *link = r->next; /* No callback can acquire this controller after unlink. */
    r->state.ssr_cancelled_before_start = true;
    r->state.ssr_start_submit_error = r->start_post_error;
    *last = r->state; /* Preserve BLOCKED/original error, never DOWN/CANCELLED. */
    *handle = NULL;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    wlan_objmgr_vdev_release_ref(vdev, WLAN_HDD_ID_OBJ_MGR);
    kfree(r);
    return 0;
}

int mishare_radio_drain(struct mishare_radio **handle, struct mishare_radio_status *last)
{
    struct mishare_radio *r, **link;
    struct mishare_radio_status s;
    unsigned long flags;
    int ret;
    if (!handle)
        return -EINVAL;
    r = *handle;
    if (!r)
        return 0;
    spin_lock_irqsave(&mishare_radio_lock, flags);
    r->state.closing = true;
    s = r->state;
    if (last)
        *last = s;
    if (s.phase == MISHARE_RADIO_BLOCKED) {
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EUCLEAN;
    }
    if (s.pending || s.users) {
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EINPROGRESS;
    }
    if (s.phase == MISHARE_RADIO_UP) {
        r->state.phase = MISHARE_RADIO_STOPPING;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        ret = radio_post(r, RADIO_STOP, NULL);
        if (ret)
            radio_block(r, ret);
        return ret ? -EUCLEAN : -EINPROGRESS;
    }
    if (s.phase != MISHARE_RADIO_DOWN && s.phase != MISHARE_RADIO_CANCELLED) {
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EINPROGRESS;
    }
    if (wlan_vdev_mlme_get_state(r->vdev) != WLAN_VDEV_S_INIT) {
        r->state.phase = MISHARE_RADIO_BLOCKED;
        r->state.error = -EUCLEAN;
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EUCLEAN;
    }
    for (link = &mishare_radios; *link && *link != r; link = &(*link)->next)
        ;
    if (!*link) {
        spin_unlock_irqrestore(&mishare_radio_lock, flags);
        return -EUCLEAN;
    }
    *link = r->next;
    *handle = NULL;
    spin_unlock_irqrestore(&mishare_radio_lock, flags);
    wlan_objmgr_vdev_release_ref(r->vdev, WLAN_HDD_ID_OBJ_MGR);
    kfree(r);
    return 0;
}
