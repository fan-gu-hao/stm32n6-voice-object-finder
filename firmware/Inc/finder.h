
#ifndef N6_FINDER_H
#define N6_FINDER_H

/* 日後由語音工作呼叫；不可在中斷中呼叫。 */
typedef enum {
  FINDER_CUP = 0,
  FINDER_BOTTLE,
  FINDER_PHONE,
  FINDER_TARGET_COUNT
} finder_target_t;

int finder_select_target(finder_target_t target);

#endif
