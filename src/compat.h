/* SPDX-License-Identifier: GPL-2.0 OR BSD-3-Clause */
/* Compatibility shims: build the rtw89 6.6-lts driver on the BELABOX/Radxa 5.10.160 kernel. */
#ifndef RTW89_COMPAT_5_10_H
#define RTW89_COMPAT_5_10_H

#include <linux/version.h>
#include <linux/stddef.h>
#include <linux/ieee80211.h>

#ifndef DECLARE_FLEX_ARRAY
#define DECLARE_FLEX_ARRAY(TYPE, NAME) \
	struct { struct { } __empty_ ## NAME; TYPE NAME[]; }
#endif

#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 12, 0)
/* No wiphy mutex before 5.12; the driver serializes with rtwdev->mutex. */
#define wiphy_lock(w) do { (void)(w); } while (0)
#define wiphy_unlock(w) do { (void)(w); } while (0)
#endif

/* Names introduced by later kernels; values are the same bits as the old names. */
#ifndef IEEE80211_HE_MAC_CAP3_MAX_AMPDU_LEN_EXP_EXT_2
#define IEEE80211_HE_MAC_CAP3_MAX_AMPDU_LEN_EXP_EXT_2	IEEE80211_HE_MAC_CAP3_MAX_AMPDU_LEN_EXP_VHT_2
#endif
#ifndef IEEE80211_HE_MAC_CAP4_AMSDU_IN_AMPDU
#define IEEE80211_HE_MAC_CAP4_AMSDU_IN_AMPDU		IEEE80211_HE_MAC_CAP4_AMDSU_IN_AMPDU
#endif
#ifndef IEEE80211_HE_PHY_CAP3_RX_PARTIAL_BW_SU_IN_20MHZ_MU
#define IEEE80211_HE_PHY_CAP3_RX_PARTIAL_BW_SU_IN_20MHZ_MU	IEEE80211_HE_PHY_CAP3_RX_HE_MU_PPDU_FROM_NON_AP_STA
#endif
#ifndef IEEE80211_HE_PHY_CAP6_TRIG_SU_BEAMFORMING_FB
#define IEEE80211_HE_PHY_CAP6_TRIG_SU_BEAMFORMING_FB	IEEE80211_HE_PHY_CAP6_TRIG_SU_BEAMFORMER_FB
#endif
#ifndef IEEE80211_HE_PHY_CAP7_POWER_BOOST_FACTOR_SUPP
#define IEEE80211_HE_PHY_CAP7_POWER_BOOST_FACTOR_SUPP	IEEE80211_HE_PHY_CAP7_POWER_BOOST_FACTOR_AR
#endif

#endif
