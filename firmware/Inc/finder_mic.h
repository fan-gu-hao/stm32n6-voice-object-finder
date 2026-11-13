#ifndef FINDER_MIC_H
#define FINDER_MIC_H

#include <stdint.h>

int finder_mic_start(void);

/* 1：取得新的一秒音訊；0：尚未準備好；-1：收音錯誤。 */
int finder_mic_take(int16_t pcm[16000]);
uint32_t finder_mic_error(void);

#endif
