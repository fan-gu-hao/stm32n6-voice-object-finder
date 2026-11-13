#ifndef FINDER_KWS_COMPARE_H
#define FINDER_KWS_COMPARE_H
#include "finder_kws.h"
/* FINDER_KWS_LIVE_CAPTURE_V1 */
#define FINDER_KWS_LIVE_CAPTURE 0
/* FINDER_KWS_COLLECT_V1 */
#define FINDER_KWS_LIVE_CASES 48U
#if FINDER_KWS_LIVE_CAPTURE
void finder_kws_live_capture(const int16_t *pcm,
                             const finder_kws_result_t *result);
#endif
#define FINDER_KWS_COMPARE_ENABLED 0
#if FINDER_KWS_COMPARE_ENABLED
void finder_kws_compare(void);
#endif
#endif
