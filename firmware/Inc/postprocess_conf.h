/*---------------------------------------------------------------------------------------------
#  * Copyright (c) 2023 STMicroelectronics.
#  * All rights reserved.
#  *
#  * This software is licensed under terms that can be found in the LICENSE file in
#  * the root directory of this software component.
#  * If no LICENSE file comes with this software, it is provided AS-IS.
#  *--------------------------------------------------------------------------------------------*/

/* ---------------    Generated code    ----------------- */
#ifndef __POSTPROCESS_CONF_H__
#define __POSTPROCESS_CONF_H__

#include "arm_math.h"

/* 使用官方 YOLOv8 實例分割後處理。 */
#define POSTPROCESS_TYPE POSTPROCESS_ISEG_YOLO_V8_UI

/* 配合目前的 256x256、COCO 80 類模型。 */
#define NB_CLASSES                          (80)
#define AI_YOLOV8_SEG_PP_TOTAL_BOXES         (1344)
#define AI_YOLOV8_SEG_PP_NB_CLASSES          (NB_CLASSES)
#define AI_YOLOV8_SEG_PP_MASK_NB              (32)
#define AI_YOLOV8_SEG_PP_MASK_SIZE            (64)

/* 結果篩選設定。 */
#define AI_YOLOV8_SEG_PP_CONF_THRESHOLD       (0.50f)
#define AI_YOLOV8_SEG_PP_IOU_THRESHOLD        (0.40f)
#define AI_YOLOV8_SEG_PP_MAX_BOXES_LIMIT      (10)

#endif /* __POSTPROCESS_CONF_H__ */
