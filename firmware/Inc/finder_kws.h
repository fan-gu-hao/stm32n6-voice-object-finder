#ifndef FINDER_KWS_H
#define FINDER_KWS_H

#include <stdint.h>

#define FINDER_KWS_SAMPLES 16000
#define FINDER_KWS_CLASSES 5

typedef struct {
  /* 順序：cup、bottle、phone、unknown、silence。 */
  float scores[FINDER_KWS_CLASSES];
  uint32_t mfcc_ms;
  uint32_t nn_ms;
} finder_kws_result_t;

/* 在 stai_runtime_init() 之後，由共用推論工作呼叫。 */
int finder_kws_init(void);

/* pcm 必須包含完整且不會被中斷覆寫的一秒錄音。
   呼叫期間不可同時執行 YOLO，也不可由中斷呼叫。 */
int finder_kws_classify(const int16_t *pcm, finder_kws_result_t *result);

#endif
