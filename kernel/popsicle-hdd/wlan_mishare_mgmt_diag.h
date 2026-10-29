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
    MDIAG_COUNT
};
void mishare_mgmt_diag_count(enum mishare_mgmt_diag_stage stage);
void mishare_mgmt_diag_frame(enum mishare_mgmt_diag_stage stage,
                            const unsigned char *frame, unsigned int length);
void mishare_mgmt_diag_registration(enum mishare_mgmt_diag_stage stage,
                                   unsigned int type, const unsigned char *prefix,
                                   unsigned int length);
#endif
