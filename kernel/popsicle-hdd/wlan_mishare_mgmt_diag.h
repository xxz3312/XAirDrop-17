/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_MISHARE_MGMT_DIAG_H
#define WLAN_MISHARE_MGMT_DIAG_H
/* Numeric counts only. No frame bytes, addresses or ownership changes. */
enum mishare_mgmt_diag_stage {
    MDIAG_REGISTER_CALLS,
    MDIAG_SKIP_INVALID,
    MDIAG_SKIP_MODE,
    MDIAG_SKIP_ML_ADAPTER,
    MDIAG_SKIP_LINK_ADAPTER,
    MDIAG_REGISTER_SUBMITTED,
    MDIAG_REGISTER_FAILED,
    MDIAG_REGISTER_BUSY,
    MDIAG_REGISTER_FAULT,
    MDIAG_UNREGISTER_CALLS,
    MDIAG_MAC_GONE,
    MDIAG_PE_ADD_SEEN,
    MDIAG_PE_DELETE_SEEN,
    MDIAG_PE_INSERTED,
    MDIAG_PE_INSERT_FAILED,
    MDIAG_PE_ALLOC_FAILED,
    MDIAG_PE_CHECK_CALLS,
    MDIAG_PE_APPLE,
    MDIAG_PE_MATCH_APPLE,
    MDIAG_PE_INDICATION_APPLE,
    MDIAG_PE_CALLBACK_APPLE,
    MDIAG_PE_NO_CALLBACK_APPLE,
    MDIAG_HDD_CALLS,
    MDIAG_HDD_BAD_LENGTH,
    MDIAG_HDD_INELIGIBLE,
    MDIAG_HDD_WRONG_LINK,
    MDIAG_HDD_NO_OWNER,
    MDIAG_HDD_BAD_FLAGS,
    MDIAG_HDD_OTHER_PREFIX,
    MDIAG_HDD_FOREIGN_DA,
    MDIAG_HDD_APPLE,
    MDIAG_REGISTER_ML_DEFAULT,
    MDIAG_HDD_STALE_IDENTITY,
    MDIAG_HDD_MISSING_VDEV,
    MDIAG_HDD_LINK_SWITCH,
    MDIAG_HDD_MLO_CONNECTION,
    MDIAG_WMA_EVENTS,
    MDIAG_WMA_BAD_HANDLE,
    MDIAG_WMA_PARAMS_ALLOC_FAIL,
    MDIAG_WMA_EXTRACT_FAIL,
    MDIAG_WMA_INVALID_BUFFER,
    MDIAG_WMA_NBUF_ALLOC_FAIL,
    MDIAG_WMA_PREPARED,
    MDIAG_WMA_ACTION,
    MDIAG_WMA_VENDOR127,
    MDIAG_WMA_APPLE,
    MDIAG_WMA_APPLE_OVER256,
    MDIAG_WMA_NO_PSOC,
    MDIAG_WMA_DISPATCH_OK,
    MDIAG_WMA_DISPATCH_FAIL,
    MDIAG_WMA_APPLE_DISPATCH_FAIL,
    MDIAG_TXRX_ENTERED,
    MDIAG_TXRX_APPLE,
    MDIAG_TXRX_BAD_TYPE,
    MDIAG_TXRX_BAD_ADDR,
    MDIAG_TXRX_APPLE_BAD_ADDR,
    MDIAG_TXRX_PROTECTED_SHORT,
    MDIAG_TXRX_UNSPECIFIED,
    MDIAG_TXRX_APPLE_UNSPECIFIED,
    MDIAG_TXRX_SIM_DROP,
    MDIAG_TXRX_HANDLER_ALLOC_FAIL,
    MDIAG_TXRX_NO_CALLBACK,
    MDIAG_TXRX_APPLE_NO_CALLBACK,
    MDIAG_TXRX_BEACON_LIMITED,
    MDIAG_TXRX_CLONE_FAIL,
    MDIAG_TXRX_APPLE_CB_ATTEMPTS,
    MDIAG_PE_ENTERED,
    MDIAG_PE_ENTRY_APPLE,
    MDIAG_PE_CAC_DROP,
    MDIAG_PE_APPLE_CAC_DROP,
    MDIAG_PE_EXTSCAN_DROP,
    MDIAG_PE_APPLE_EXTSCAN_DROP,
    MDIAG_PE_NO_SESSION_DROP,
    MDIAG_PE_APPLE_NO_SESSION_DROP,
    MDIAG_PE_BAD_PACKET,
    MDIAG_COUNT
};
/* Numeric prefix classification only; no identity/TLV validation.
 * Length supplied by the native owning buffer, at most the supported 2304. */
#define MDIAG_CLASS_ACTION 1U
#define MDIAG_CLASS_VENDOR127 2U
#define MDIAG_CLASS_APPLE 4U
static inline unsigned int
mishare_mgmt_frame_class(const unsigned char *f, unsigned int length)
{
    unsigned int result;
    if (!f || length < 24 || length > 2304 || f[0] != 0xd0)
        return 0;
    result = MDIAG_CLASS_ACTION;
    if (length >= 25 && f[24] == 127) {
        result |= MDIAG_CLASS_VENDOR127;
        if (length >= 29 && !f[25] && f[26] == 0x17 &&
            f[27] == 0xf2 && f[28] == 8)
            result |= MDIAG_CLASS_APPLE;
    }
    return result;
}
void mishare_mgmt_diag_count(enum mishare_mgmt_diag_stage stage);
void mishare_mgmt_diag_frame(enum mishare_mgmt_diag_stage stage,
                            const unsigned char *frame, unsigned int length);
void mishare_mgmt_diag_registration(enum mishare_mgmt_diag_stage stage,
                                   unsigned int type, const unsigned char *prefix,
                                   unsigned int length);
#endif
