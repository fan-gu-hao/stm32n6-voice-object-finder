from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
app = root / "firmware/Src/app.c"
header = root / "firmware/Inc/finder.h"
old = app.read_text(encoding="utf-8")
marker = "FINDER_VISION_APP_V2"

if marker in old:
    print("應用流程已更新，請繼續下一段。")
    raise SystemExit(0)

if "FINDER_YOLO_MODEL_DATA_V1" not in old:
    raise SystemExit("找不到上一個步驟的修改，尚未寫入。")

def keep(start, end=None):
    if old.count(start) != 1 or (end and old.count(end) != 1):
        raise SystemExit(f"原始碼位置與預期不同：{start}")
    a = old.index(start)
    b = old.index(end, a) if end else len(old)
    return old[a:b]

# 保留官方硬體與工作管理流程。
license_text = old[:old.index('#include "app.h"')]
cache = keep("static int is_cache_enable()", "static float pd_normalize_angle")
queues = keep("static int bqueue_init", "static int clamp_point(")
drawing = keep("static void dp_update_drawing_area", "static void on_ld_toggle_button_click")
tail = keep("static void isp_thread_fct")

tail = tail.replace("  cpuload_init(&cpu_load);\n", "")
queues = queues.replace("  frame_event_nb++;\n", "")
queues = queues.replace("    frame_event_nb_for_resize = frame_event_nb - 1;\n", "")
queues = queues.replace(
    "    /* minus 1 since app_main_pipe_frame_event occur before app_ancillary_pipe_frame_event() */\n",
    "",
)

# 攝影機回呼在中斷中執行，使用對應的信號量介面。
old_take = "  ret = xSemaphoreTake(bq->free, is_blocking ? portMAX_DELAY : 0);"
new_take = """  if (xPortIsInsideInterrupt()) {
    BaseType_t woken = pdFALSE;
    ret = xSemaphoreTakeFromISR(bq->free, &woken);
    portYIELD_FROM_ISR(woken);
  } else {
    ret = xSemaphoreTake(bq->free, is_blocking ? portMAX_DELAY : 0);
  }"""

if queues.count(old_take) != 1:
    raise SystemExit("找不到官方佇列修改位置，尚未寫入。")

queues = queues.replace(old_take, new_take, 1)

declarations = r'''
#include "app.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "app_cam.h"
#include "app_config.h"
#include "finder.h"
#include "app_postprocess.h"
#include "stai_network.h"
#include "ll_aton_osal.h"
#include "cmw_camera.h"
#include "scrl.h"
#include "stm32n6570_discovery.h"
#include "stm32_lcd.h"
#include "stm32_lcd_ex.h"
#include "stm32n6xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "utils.h"

#define FREERTOS_PRIORITY(p) ((UBaseType_t)((int)tskIDLE_PRIORITY + configMAX_PRIORITIES / 2 + (p)))
#define LCD_FG_WIDTH LCD_BG_WIDTH
#define LCD_FG_HEIGHT LCD_BG_HEIGHT
#define DISPLAY_BUFFER_NB (DISPLAY_DELAY + 2)
#define BQUEUE_MAX_BUFFERS 2
#define LCD_FONT Font20
#define UTIL_LCD_COLOR_TRANSPARENT 0
#define FINDER_CONFIRM_FRAMES 2U
#define FINDER_CONFIRM_IOU (0.30f)
#define MASK_BYTES (AI_YOLOV8_SEG_PP_MASK_SIZE * AI_YOLOV8_SEG_PP_MASK_SIZE)
#define CACHE_OP(op) do { if (is_cache_enable()) { op; } } while (0)

_Static_assert(STAI_NETWORK_IN_NUM == 1, "Expected one camera input");
_Static_assert(STAI_NETWORK_IN_1_WIDTH == 256 &&
               STAI_NETWORK_IN_1_HEIGHT == 256, "Expected 256x256 input");
_Static_assert(STAI_NETWORK_IN_1_CHANNEL == 3 &&
               STAI_NETWORK_IN_1_FORMAT == STAI_FORMAT_U8, "Expected RGB uint8");
_Static_assert(STAI_NETWORK_OUT_NUM == 2, "Expected two YOLO outputs");
_Static_assert(STAI_NETWORK_OUT_1_FORMAT == STAI_FORMAT_S8 &&
               STAI_NETWORK_OUT_2_FORMAT == STAI_FORMAT_S8, "Expected int8 outputs");

typedef struct {
  uint32_t X0, Y0, XSize, YSize;
} Rectangle_TypeDef;

typedef struct {
  SemaphoreHandle_t free;
  StaticSemaphore_t free_buffer;
  SemaphoreHandle_t ready;
  StaticSemaphore_t ready_buffer;
  int buffer_nb;
  uint8_t *buffers[BQUEUE_MAX_BUFFERS];
  int free_idx, ready_idx;
} bqueue_t;

typedef struct {
  unsigned target;
  uint32_t generation;
  int found;
  uint32_t nn_ms, pp_ms, period_ms;
  iseg_pp_outBuffer_t box;
} display_info_t;

typedef struct {
  SemaphoreHandle_t update;
  StaticSemaphore_t update_buffer;
  SemaphoreHandle_t lock;
  StaticSemaphore_t lock_buffer;
  display_info_t info;
} display_t;

typedef struct {
  stai_network_info network_info;
  stai_ptr nn_in;
  stai_ptr nn_out[STAI_NETWORK_OUT_NUM];
  iseg_yolov8_pp_static_param_t static_param;
  iseg_pp_out_t output;
} yolo_model_info_t;

static const int target_classes[FINDER_TARGET_COUNT] = {41, 39, 67};
static const char *const target_names[FINDER_TARGET_COUNT] = {"CUP", "BOTTLE", "PHONE"};
static Rectangle_TypeDef lcd_bg_area = {0, 0, LCD_BG_WIDTH, LCD_BG_HEIGHT};
static Rectangle_TypeDef lcd_fg_area = {0, 0, LCD_FG_WIDTH, LCD_FG_HEIGHT};

static uint8_t lcd_bg_buffer[DISPLAY_BUFFER_NB][LCD_BG_WIDTH * LCD_BG_HEIGHT * DISPLAY_BPP] ALIGN_32 IN_PSRAM;
static int lcd_bg_buffer_disp_idx = 1;
static int lcd_bg_buffer_capt_idx;
static uint8_t lcd_fg_buffer[2][LCD_FG_WIDTH * LCD_FG_HEIGHT * 2] ALIGN_32 IN_PSRAM;
static int lcd_fg_buffer_rd_idx;
static uint8_t screen_buffer[LCD_BG_WIDTH * LCD_BG_HEIGHT * 2] ALIGN_32 IN_PSRAM;
static display_t disp;

/* 複製遮罩，避免下一次推論改寫顯示中的結果。 */
static uint8_t result_mask[MASK_BYTES] ALIGN_32 IN_PSRAM;
static uint8_t drawing_mask[MASK_BYTES] ALIGN_32 IN_PSRAM;

static uint8_t network_ctx[STAI_NETWORK_CONTEXT_SIZE] ALIGN_32;
static uint8_t nn_input_buffers[2][STAI_NETWORK_IN_1_SIZE_BYTES] ALIGN_32 IN_PSRAM;
static bqueue_t nn_input_queue;
static yolo_model_info_t yolo_info;

static StaticTask_t nn_thread, dp_thread, isp_thread;
static StackType_t nn_thread_stack[2 * configMINIMAL_STACK_SIZE];
static StackType_t dp_thread_stack[2 * configMINIMAL_STACK_SIZE];
static StackType_t isp_thread_stack[2 * configMINIMAL_STACK_SIZE];
static SemaphoreHandle_t isp_sem;
static StaticSemaphore_t isp_sem_buffer;

'''

functions = r'''
int finder_select_target(finder_target_t target)
{
  if ((unsigned)target >= FINDER_TARGET_COUNT || !disp.lock)
    return -1;

  int ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
  assert(ret == pdTRUE);
  disp.info.target = target;
  disp.info.generation++;
  disp.info.found = 0;
  ret = xSemaphoreGive(disp.lock);
  assert(ret == pdTRUE);
  xSemaphoreGive(disp.update);
  return 0;
}

static float box_iou(const iseg_pp_outBuffer_t *a, const iseg_pp_outBuffer_t *b)
{
  float left = fmaxf(a->x_center - a->width * .5f, b->x_center - b->width * .5f);
  float right = fminf(a->x_center + a->width * .5f, b->x_center + b->width * .5f);
  float top = fmaxf(a->y_center - a->height * .5f, b->y_center - b->height * .5f);
  float bottom = fminf(a->y_center + a->height * .5f, b->y_center + b->height * .5f);
  float intersection = fmaxf(0, right - left) * fmaxf(0, bottom - top);
  float area = a->width * a->height + b->width * b->height - intersection;
  return area > 0 ? intersection / area : 0;
}

static void run_yolo(void)
{
  stai_return_code ret;
  do {
    ret = stai_network_run(network_ctx, STAI_MODE_ASYNC);
    if (ret == STAI_RUNNING_WFE)
      LL_ATON_OSAL_WFE();
  } while (ret == STAI_RUNNING_WFE || ret == STAI_RUNNING_NO_WFE);

  assert(ret == STAI_DONE);
  ret = stai_ext_network_new_inference(network_ctx);
  assert(ret == STAI_SUCCESS);
}

static void nn_thread_fct(void *arg)
{
  (void)arg;
  stai_network_info *info = &yolo_info.network_info;
  stai_ptr *outputs = yolo_info.nn_out;
  stai_size input_count = 1, output_count = STAI_NETWORK_OUT_NUM;
  iseg_pp_outBuffer_t previous = {0};
  unsigned hits = 0;
  uint32_t previous_generation = UINT32_MAX;
  uint32_t last_start = 0, last_log = 0;

  int ret = stai_runtime_init();
  assert(ret == STAI_SUCCESS);
  ret = stai_network_init(network_ctx);
  assert(ret == STAI_SUCCESS);
  ret = stai_network_get_info(network_ctx, info);
  assert(ret == STAI_SUCCESS);
  assert(info->n_inputs == 1 && info->n_outputs == STAI_NETWORK_OUT_NUM);
  assert(info->inputs[0].size_bytes == sizeof(nn_input_buffers[0]));

  ret = stai_network_get_inputs(network_ctx, &yolo_info.nn_in, &input_count);
  assert(ret == STAI_SUCCESS && yolo_info.nn_in && input_count == 1);
  ret = stai_network_get_outputs(network_ctx, outputs, &output_count);
  assert(ret == STAI_SUCCESS && output_count == STAI_NETWORK_OUT_NUM);
  ret = app_postprocess_init(&yolo_info.static_param, info);
  assert(ret == 0);

  CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(nn_input_buffers, sizeof(nn_input_buffers)));
  uint8_t *first = bqueue_get_free(&nn_input_queue, 0);
  assert(first);
  printf("Finder: YOLO ready; USER1 selects CUP / BOTTLE / PHONE\n");
  CAM_NNPipe_Start(first, CMW_MODE_CONTINUOUS);

  while (1) {
    uint8_t *capture = bqueue_get_ready(&nn_input_queue);
    assert(capture);
    uint32_t start = HAL_GetTick();
    uint32_t period = last_start ? start - last_start : 0;
    last_start = start;

    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);
    unsigned target = disp.info.target;
    uint32_t generation = disp.info.generation;
    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);

    /* 複製到模型產碼所配置的輸入區，完成後歸還攝影機緩衝區。 */
    CACHE_OP(SCB_InvalidateDCache_by_Addr(capture, sizeof(nn_input_buffers[0])));
    memcpy(yolo_info.nn_in, capture, sizeof(nn_input_buffers[0]));
    CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(yolo_info.nn_in, info->inputs[0].size_bytes));
    bqueue_put_free(&nn_input_queue);

    uint32_t ts = HAL_GetTick();
    run_yolo();
    uint32_t nn_ms = HAL_GetTick() - ts;

    for (unsigned i = 0; i < output_count; i++)
      CACHE_OP(SCB_InvalidateDCache_by_Addr(outputs[i], info->outputs[i].size_bytes));

    ts = HAL_GetTick();
    ret = app_postprocess_run((void **)outputs, output_count,
                             &yolo_info.output, &yolo_info.static_param);
    assert(ret == 0);
    uint32_t pp_ms = HAL_GetTick() - ts;

    /* 從原本的 80 類辨識結果中篩選指定物件。 */
    iseg_pp_outBuffer_t *best = NULL;
    for (int i = 0; i < yolo_info.output.nb_detect; i++) {
      iseg_pp_outBuffer_t *box = &yolo_info.output.pOutBuff[i];
      if (box->class_index == target_classes[target] &&
          box->conf >= AI_YOLOV8_SEG_PP_CONF_THRESHOLD &&
          (!best || box->conf > best->conf))
        best = box;
    }

    if (generation != previous_generation) {
      hits = 0;
      previous_generation = generation;
    }
    if (!best) {
      hits = 0;
    } else {
      hits = hits && box_iou(best, &previous) >= FINDER_CONFIRM_IOU ? hits + 1 : 1;
      hits = MIN(hits, FINDER_CONFIRM_FRAMES);
      previous = *best;
      previous.pMask = NULL;
    }

    int found = best && hits >= FINDER_CONFIRM_FRAMES;
    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);

    /* 若推論途中切換目標，捨棄舊目標的結果。 */
    if (generation == disp.info.generation) {
      disp.info.found = found;
      disp.info.nn_ms = nn_ms;
      disp.info.pp_ms = pp_ms;
      disp.info.period_ms = period;
      if (found) {
        disp.info.box = *best;
        disp.info.box.pMask = NULL;
        memcpy(result_mask, best->pMask, MASK_BYTES);
      }
    }

    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);
    xSemaphoreGive(disp.update);

    for (unsigned i = 0; i < output_count; i++)
      CACHE_OP(SCB_InvalidateDCache_by_Addr(outputs[i], info->outputs[i].size_bytes));

    if (HAL_GetTick() - last_log >= 1000) {
      last_log = HAL_GetTick();
      printf("FINDER,target=%s,found=%d,score=%u,nn_ms=%lu,pp_ms=%lu\n",
             target_names[target], found, found ? (unsigned)(best->conf * 100) : 0,
             (unsigned long)nn_ms, (unsigned long)pp_ms);
    }
  }
}

static int clamp_coord(int value, int low, int high)
{
  return MAX(low, MIN(high, value));
}

static void Display_NetworkOutput(const display_info_t *info)
{
  const int side = LCD_BG_HEIGHT;
  const int left = (LCD_BG_WIDTH - side) / 2;

  UTIL_LCD_Clear(UTIL_LCD_COLOR_TRANSPARENT);
  UTIL_LCD_DrawRect(left, 0, side - 1, side - 1, UTIL_LCD_COLOR_WHITE);

  if (info->found) {
    const iseg_pp_outBuffer_t *b = &info->box;
    int x0 = left + clamp_coord((int)((b->x_center - b->width / 2) * side), 0, side - 1);
    int y0 = clamp_coord((int)((b->y_center - b->height / 2) * side), 0, side - 1);
    int x1 = left + clamp_coord((int)((b->x_center + b->width / 2) * side), 0, side - 1);
    int y1 = clamp_coord((int)((b->y_center + b->height / 2) * side), 0, side - 1);

    for (int y = 0; y < AI_YOLOV8_SEG_PP_MASK_SIZE; y++) {
      for (int x = 0; x < AI_YOLOV8_SEG_PP_MASK_SIZE; x++) {
        if (!drawing_mask[y * AI_YOLOV8_SEG_PP_MASK_SIZE + x])
          continue;

        int mx0 = MAX(x0, left + x * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int my0 = MAX(y0, y * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int mx1 = MIN(x1 + 1, left + (x + 1) * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int my1 = MIN(y1 + 1, (y + 1) * side / AI_YOLOV8_SEG_PP_MASK_SIZE);

        if (mx1 > mx0 && my1 > my0)
          UTIL_LCD_FillRect(mx0, my0, mx1 - mx0, my1 - my0, 0x6000FF00);
      }
    }

    if (x1 > x0 && y1 > y0)
      UTIL_LCD_DrawRect(x0, y0, x1 - x0, y1 - y0, UTIL_LCD_COLOR_GREEN);
  }

  UTIL_LCD_SetBackColor(0xC0000000);
  UTIL_LCD_SetTextColor(UTIL_LCD_COLOR_WHITE);
  UTIL_LCDEx_PrintfAt(0, LINE(0), CENTER_MODE, "Object Finder - vision stage");
  UTIL_LCDEx_PrintfAt(0, LINE(1), CENTER_MODE, "Target: %s  %s  Score: %u%%",
                     target_names[info->target], info->found ? "FOUND" : "SEARCHING",
                     info->found ? (unsigned)(info->box.conf * 100) : 0);
  UTIL_LCDEx_PrintfAt(0, LINE(17), CENTER_MODE, "Place object inside the square");
  UTIL_LCDEx_PrintfAt(0, LINE(18), CENTER_MODE, "USER1: change target | Voice: pending");
  UTIL_LCDEx_PrintfAt(0, LINE(19), CENTER_MODE, "NN: %lu ms  PP: %lu ms  Update: %lu ms",
                     (unsigned long)info->nn_ms, (unsigned long)info->pp_ms,
                     (unsigned long)info->period_ms);
  UTIL_LCD_SetBackColor(0);
}

'''

display_thread = r'''
static void dp_thread_fct(void *arg)
{
  (void)arg;
  display_info_t info;
  int ret = BSP_PB_Init(BUTTON_USER1, BUTTON_MODE_GPIO);
  assert(ret == BSP_ERROR_NONE);
  int previous_button = BSP_PB_GetState(BUTTON_USER1);
  uint32_t last_button = HAL_GetTick();

  while (1) {
    xSemaphoreTake(disp.update, pdMS_TO_TICKS(100));
    int button = BSP_PB_GetState(BUTTON_USER1);

    if (button && !previous_button && HAL_GetTick() - last_button >= 200) {
      ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
      assert(ret == pdTRUE);
      unsigned next = (disp.info.target + 1) % FINDER_TARGET_COUNT;
      ret = xSemaphoreGive(disp.lock);
      assert(ret == pdTRUE);
      finder_select_target((finder_target_t)next);
      last_button = HAL_GetTick();
    }
    previous_button = button;

    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);
    info = disp.info;
    if (info.found)
      memcpy(drawing_mask, result_mask, MASK_BYTES);
    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);

    dp_update_drawing_area();
    Display_NetworkOutput(&info);
    CACHE_OP(SCB_CleanDCache_by_Addr(lcd_fg_buffer[lcd_fg_buffer_rd_idx],
                                    sizeof(lcd_fg_buffer[0])));
    dp_commit_drawing_area();
  }
}

'''

public_header = r'''
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
'''

updated = (
    license_text + "/* FINDER_VISION_APP_V2 */\n"
    + declarations + cache + queues + functions
    + drawing + display_thread + tail
)

backup = root / "backups" / datetime.now().strftime(
    "vision_app_%Y%m%d_%H%M%S_%f"
)
backup.mkdir(parents=True)
shutil.copy2(app, backup / "app.c")

if header.exists():
    shutil.copy2(header, backup / "finder.h")

app.write_text(updated, encoding="utf-8")
header.write_text(public_header, encoding="utf-8")

print("已更新：", app)
print("已新增目標切換介面：", header)
print("備份：", backup)
print("完成：YOLO 推論、USER1 選物、遮罩顯示已接入。")
