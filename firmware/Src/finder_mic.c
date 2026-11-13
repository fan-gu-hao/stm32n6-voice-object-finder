/* FINDER_MIC_LIVE_V1 */
#include "finder_mic.h"
#include "app_config.h"
#include "stm32n6xx_hal.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define BLOCK 256U
#define RING 32768U
#define WINDOW 16000U
#define HOP 3200U

static MDF_HandleTypeDef mic;
static DMA_HandleTypeDef dma;
static DMA_QListTypeDef queue;

static struct {
  DMA_NodeTypeDef value;
  uint8_t padding[64U - sizeof(DMA_NodeTypeDef)];
} node __attribute__((aligned(64)));

static int16_t dma_pcm[2U * BLOCK] __attribute__((aligned(32)));
static int16_t ring_pcm[RING] __attribute__((aligned(32)));
static volatile uint32_t written, fatal_error;
static uint32_t last_window, warmup;

static void cache_prepare(void *p, uint32_t n)
{
#if defined(USE_DCACHE)
  SCB_CleanInvalidateDCache_by_Addr(p, (int32_t)n);
#endif
}

static void receive_block(int16_t *p)
{
#if defined(USE_DCACHE)
  SCB_InvalidateDCache_by_Addr(p, BLOCK * sizeof(int16_t));
#endif

  if (warmup) {
    warmup--;
    return;
  }

  uint32_t count = written;
  memcpy(&ring_pcm[count & (RING - 1U)],
         p, BLOCK * sizeof(int16_t));
  __DMB();
  written = count + BLOCK;
}

void HAL_MDF_AcqHalfCpltCallback(MDF_HandleTypeDef *h)
{
  if (h == &mic) receive_block(dma_pcm);
}

void HAL_MDF_AcqCpltCallback(MDF_HandleTypeDef *h)
{
  if (h == &mic) receive_block(dma_pcm + BLOCK);
}

void HAL_MDF_ErrorCallback(MDF_HandleTypeDef *h)
{
  if (h == &mic)
    fatal_error |= h->ErrorCode & ~MDF_ERROR_SATURATION;
}

void GPDMA1_Channel6_IRQHandler(void)
{
  HAL_DMA_IRQHandler(&dma);
}

void MDF1_FLT0_IRQHandler(void)
{
  HAL_MDF_IRQHandler(&mic);
}

uint32_t finder_mic_error(void)
{
  return fatal_error;
}

int finder_mic_take(int16_t pcm[16000])
{
  if (fatal_error) return -1;

  uint32_t end = written;
  __DMB();
  if (end < WINDOW || end - last_window < HOP) return 0;

  uint32_t begin = (end - WINDOW) & (RING - 1U);
  uint32_t n = RING - begin;
  if (n > WINDOW) n = WINDOW;

  memcpy(pcm, ring_pcm + begin, n * sizeof(int16_t));
  memcpy(pcm + n, ring_pcm, (WINDOW - n) * sizeof(int16_t));
  __DMB();

  /* 若複製期間工作被延遲太久，捨棄這次快照。 */
  if (written - end >= RING - WINDOW) return 0;

  last_window = end;
  return 1;
}

int finder_mic_start(void)
{
  RCC_PeriphCLKInitTypeDef clk = {0};
  GPIO_InitTypeDef gpio = {0};
  DMA_NodeConfTypeDef cfg = {0};
  MDF_FilterConfigTypeDef filter = {0};
  MDF_DmaConfigTypeDef transfer = {0};

  /* 現有 PLL2 = 1 GHz，僅設定麥克風使用的 IC8 分頻器。 */
  clk.PeriphClockSelection = RCC_PERIPHCLK_MDF1;
  clk.Mdf1ClockSelection = RCC_MDF1CLKSOURCE_IC8;
  clk.ICSelection[RCC_IC8].ClockSelection = RCC_ICCLKSOURCE_PLL2;
  clk.ICSelection[RCC_IC8].ClockDivider = 61;
  if (HAL_RCCEx_PeriphCLKConfig(&clk) != HAL_OK) return -1;

  uint32_t kernel = HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_MDF1);
  if (kernel < 16300000U || kernel > 16500000U) return -2;

  __HAL_RCC_MDF1_CLK_ENABLE();
  __HAL_RCC_MDF1_FORCE_RESET();
  __HAL_RCC_MDF1_RELEASE_RESET();
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPDMA1_CLK_ENABLE();
  __HAL_RCC_RIFSC_CLK_ENABLE();

  HAL_RIF_RISC_SetSlaveSecureAttributes(
      RIF_RISC_PERIPH_INDEX_MDF1,
      RIF_ATTRIBUTE_SEC | RIF_ATTRIBUTE_PRIV);

  HAL_GPIO_ConfigPinAttributes(
      GPIOE, GPIO_PIN_2 | GPIO_PIN_8,
      GPIO_PIN_SEC | GPIO_PIN_NPRIV);

  gpio.Pin = GPIO_PIN_2 | GPIO_PIN_8;
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
  gpio.Alternate = GPIO_AF4_MDF1;
  HAL_GPIO_Init(GPIOE, &gpio);

  mic.Instance = MDF1_Filter0;
  mic.Init.CommonParam.InterleavedFilters = 0;
  mic.Init.CommonParam.ProcClockDivider = 1;
  mic.Init.CommonParam.OutputClock.Activation = ENABLE;
  mic.Init.CommonParam.OutputClock.Pins = MDF_OUTPUT_CLOCK_0;
  mic.Init.CommonParam.OutputClock.Divider = 8;
  mic.Init.CommonParam.OutputClock.Trigger.Activation = DISABLE;
  mic.Init.SerialInterface.Activation = ENABLE;
  mic.Init.SerialInterface.Mode = MDF_SITF_NORMAL_SPI_MODE;
  mic.Init.SerialInterface.ClockSource = MDF_SITF_CCK0_SOURCE;
  mic.Init.SerialInterface.Threshold = 31;
  mic.Init.FilterBistream = MDF_BITSTREAM0_FALLING;
  if (HAL_MDF_Init(&mic) != HAL_OK) return -3;

  cfg.NodeType = DMA_GPDMA_LINEAR_NODE;
  cfg.Init.Request = GPDMA1_REQUEST_MDF1_FLT0;
  cfg.Init.BlkHWRequest = DMA_BREQ_SINGLE_BURST;
  cfg.Init.Direction = DMA_PERIPH_TO_MEMORY;
  cfg.Init.SrcInc = DMA_SINC_FIXED;
  cfg.Init.DestInc = DMA_DINC_INCREMENTED;
  cfg.Init.SrcDataWidth = DMA_SRC_DATAWIDTH_HALFWORD;
  cfg.Init.DestDataWidth = DMA_DEST_DATAWIDTH_HALFWORD;
  cfg.Init.SrcBurstLength = 1;
  cfg.Init.DestBurstLength = 1;
  cfg.Init.TransferAllocatedPort =
      DMA_SRC_ALLOCATED_PORT0 | DMA_DEST_ALLOCATED_PORT1;
  cfg.Init.TransferEventMode = DMA_TCEM_BLOCK_TRANSFER;
  cfg.Init.Mode = DMA_NORMAL;
  cfg.TriggerConfig.TriggerPolarity = DMA_TRIG_POLARITY_MASKED;
  cfg.DataHandlingConfig.DataExchange = DMA_EXCHANGE_NONE;
  cfg.DataHandlingConfig.DataAlignment = DMA_DATA_RIGHTALIGN_ZEROPADDED;
  cfg.SrcSecure = DMA_CHANNEL_SRC_SEC;
  cfg.DestSecure = DMA_CHANNEL_DEST_SEC;

  /* 與 HAL_MDF_AcqStart_DMA 使用的位址和長度一致。 */
  cfg.SrcAddress = (uint32_t)&MDF1_Filter0->DFLTDR + 2U;
  cfg.DstAddress = (uint32_t)dma_pcm;
  cfg.DataSize = sizeof(dma_pcm);

  if (HAL_DMAEx_List_BuildNode(&cfg, &node.value) != HAL_OK) return -4;
  if (HAL_DMAEx_List_InsertNode(&queue, NULL, &node.value) != HAL_OK)
    return -5;
  if (HAL_DMAEx_List_SetCircularMode(&queue) != HAL_OK) return -6;

  dma.Instance = GPDMA1_Channel6;
  dma.InitLinkedList.Priority = DMA_LOW_PRIORITY_HIGH_WEIGHT;
  dma.InitLinkedList.LinkStepMode = DMA_LSM_FULL_EXECUTION;
  dma.InitLinkedList.LinkAllocatedPort = DMA_LINK_ALLOCATED_PORT0;
  dma.InitLinkedList.TransferEventMode = DMA_TCEM_BLOCK_TRANSFER;
  dma.InitLinkedList.LinkedListMode = DMA_LINKEDLIST_CIRCULAR;

  if (HAL_DMAEx_List_Init(&dma) != HAL_OK) return -7;
  if (HAL_DMAEx_List_LinkQ(&dma, &queue) != HAL_OK) return -8;
  if (HAL_DMA_ConfigChannelAttributes(
          &dma, DMA_CHANNEL_SEC | DMA_CHANNEL_PRIV |
                DMA_CHANNEL_SRC_SEC | DMA_CHANNEL_DEST_SEC) != HAL_OK)
    return -9;

  __HAL_LINKDMA(&mic, hdma, dma);

  /* 與訓練錄音相同的濾波器、抽取倍率和增益。 */
  filter.DataSource = MDF_DATA_SOURCE_BSMX;
  filter.CicMode = MDF_ONE_FILTER_SINC4;
  filter.DecimationRatio = 32;
  filter.Gain = 14;
  filter.ReshapeFilter.Activation = ENABLE;
  filter.ReshapeFilter.DecimationRatio = MDF_RSF_DECIMATION_RATIO_4;
  filter.HighPassFilter.Activation = ENABLE;
  filter.HighPassFilter.CutOffFrequency = MDF_HPF_CUTOFF_0_000625FPCM;
  filter.AcquisitionMode = MDF_MODE_ASYNC_CONT;
  filter.FifoThreshold = MDF_FIFO_THRESHOLD_NOT_EMPTY;

  written = last_window = fatal_error = 0;
  warmup = 16;

  cache_prepare(dma_pcm, sizeof(dma_pcm));
  cache_prepare(&node, sizeof(node));

  HAL_NVIC_SetPriority(GPDMA1_Channel6_IRQn, 6, 0);
  HAL_NVIC_SetPriority(MDF1_FLT0_IRQn, 6, 0);
  HAL_NVIC_ClearPendingIRQ(GPDMA1_Channel6_IRQn);
  HAL_NVIC_ClearPendingIRQ(MDF1_FLT0_IRQn);
  HAL_NVIC_EnableIRQ(GPDMA1_Channel6_IRQn);
  HAL_NVIC_EnableIRQ(MDF1_FLT0_IRQn);

  transfer.Address = (uint32_t)dma_pcm;
  transfer.DataLength = sizeof(dma_pcm);
  transfer.MsbOnly = ENABLE;
  if (HAL_MDF_AcqStart_DMA(&mic, &filter, &transfer) != HAL_OK)
    return -10;

  printf("MIC,rate=%lu,pdm=%lu\n",
         (unsigned long)(kernel / 1024U),
         (unsigned long)(kernel / 8U));
  return 0;
}
