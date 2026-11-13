/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include <stdio.h>
#include <string.h>

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "stm32n6570_discovery.h"
#include "stm32n6570_discovery_bus.h"
#include "audio.h"
#include "wm8904.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

MDF_HandleTypeDef MdfHandle0;
MDF_FilterConfigTypeDef MdfFilterConfig0;
DMA_NodeTypeDef Node_GPDMA1_Channel6 __NON_CACHEABLE;
DMA_QListTypeDef List_GPDMA1_Channel6;
DMA_HandleTypeDef handle_GPDMA1_Channel6;

/* USER CODE BEGIN PV */
static int16_t PcmBuffer[2048U] __NON_CACHEABLE;




SAI_HandleTypeDef hsai_BlockA1;
DMA_NodeTypeDef pNode_GPDMACH0 __NON_CACHEABLE;
DMA_QListTypeDef pQueueLinkList_GPDMACH0;
DMA_HandleTypeDef handle_GPDMA1_Channel0;

static AUDIO_Drv_t *Audio_Drv = NULL;
static void *Audio_CompObj;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_GPDMA1_Init(void);
static void MX_MDF1_Init(void);
static void SystemIsolation_Config(void);
/* USER CODE BEGIN PFP */
static void MPU_Config(void);
static void WM8904_Probe(void);
static void MX_SAI1_Init(void);
static void Playback_Init(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */

/* N6_MIC_WAV_V1: 先錄音到 RAM，再由主迴圈傳回電腦。 */
#define MIC_SAMPLES 80000U
static int16_t MicAudio[MIC_SAMPLES];
static volatile uint32_t MicCount, MicSkip, MicActive, MicFailed;

static void MicTx(const void *data, uint32_t size)
{
  const uint8_t *p = (const uint8_t *)data;
  while (size != 0U)
  {
    uint16_t n = (size > 4096U) ? 4096U : (uint16_t)size;
    if (HAL_UART_Transmit(&hcom_uart[COM1], (uint8_t *)p, n, 2000U) != HAL_OK)
      Error_Handler();
    p += n;
    size -= n;
  }
}

static void MicLine(const char *text)
{
  MicTx(text, (uint32_t)strlen(text));
}

/* 中斷只複製樣本，不在這裡傳送串列資料。 */
static void MicCopy(const int16_t *samples)
{
  if (MicActive == 0U || MicFailed != 0U) return;
  if (MicSkip != 0U)
  {
    --MicSkip;
    return;
  }
  uint32_t offset = MicCount;
  uint32_t n = MIC_SAMPLES - offset;
  if (n > 1024U) n = 1024U;
  memcpy(&MicAudio[offset], samples, n * sizeof(int16_t));
  __DMB();
  MicCount = offset + n;
  if (MicCount == MIC_SAMPLES) MicActive = 0U;
}

static uint32_t MicCrc32(const uint8_t *data, uint32_t size)
{
  uint32_t crc = 0xFFFFFFFFU;
  for (uint32_t i = 0U; i < size; ++i)
  {
    crc ^= data[i];
    for (uint32_t bit = 0U; bit < 8U; ++bit)
      crc = (crc >> 1) ^ ((0U - (crc & 1U)) & 0xEDB88320U);
  }
  return ~crc;
}

static void MicRecord(void)
{
  MDF_DmaConfigTypeDef dma = {0};
  char header[96];
  MicCount = 0U;
  MicSkip = 2U;  /* 略過啟動後前兩個區塊，約 128 毫秒。 */
  MicFailed = 0U;
  BSP_LED_Off(LED_RED);
  MicLine("N6MIC_RECORDING,80000\n");
  BSP_LED_On(LED_GREEN);
  dma.Address = (uint32_t)(uintptr_t)PcmBuffer;
  dma.DataLength = sizeof(PcmBuffer);
  dma.MsbOnly = ENABLE;
  MdfHandle0.ErrorCode = MDF_ERROR_NONE;
  MicActive = 1U;
  uint32_t started = HAL_GetTick();

  if (HAL_MDF_AcqStart_DMA(&MdfHandle0, &MdfFilterConfig0, &dma) != HAL_OK)
  {
    MicActive = 0U;
    BSP_LED_Off(LED_GREEN);
    MicLine("N6MIC_ERROR,START\n");
    Error_Handler();
  }

  while (MicActive != 0U)
  {
    if ((uint32_t)(HAL_GetTick() - started) > 12000U)
    {
      MicFailed = 1U;
      MicActive = 0U;
      break;
    }
    HAL_Delay(1U);
  }

  /* 收完或失敗後，在主迴圈停止 DMA。 */
  if (HAL_MDF_AcqStop_DMA(&MdfHandle0) != HAL_OK)
  {
    BSP_LED_Off(LED_GREEN);
    MicLine("N6MIC_ERROR,STOP\n");
    Error_Handler();
  }
  __DMB();
  BSP_LED_Off(LED_GREEN);

  if (MicFailed != 0U || MicCount != MIC_SAMPLES)
  {
    BSP_LED_On(LED_RED);
    MicLine("N6MIC_ERROR,CAPTURE\n");
    return;
  }

  uint32_t crc = MicCrc32((const uint8_t *)MicAudio, sizeof(MicAudio));
  int n = snprintf(header, sizeof(header),
                   "N6MIC_DATA,16000,1,16,%lu,%08lX\n",
                   (unsigned long)sizeof(MicAudio), (unsigned long)crc);
  if (n <= 0 || (unsigned int)n >= sizeof(header)) Error_Handler();
  MicTx(header, (uint32_t)n);
  MicTx(MicAudio, sizeof(MicAudio));
  MicLine("\nN6MIC_DONE\n");
}

int main(void)
{
  COM_InitTypeDef com = {0};
  MPU_Config();
  SCB_EnableICache();
  SCB_EnableDCache();
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_GPDMA1_Init();
  MX_MDF1_Init();
  SystemIsolation_Config();

  if (BSP_LED_Init(LED_RED) != BSP_ERROR_NONE ||
      BSP_LED_Init(LED_GREEN) != BSP_ERROR_NONE) Error_Handler();

  BSP_LED_Off(LED_RED);
  BSP_LED_Off(LED_GREEN);
  com.BaudRate = 115200U;
  com.WordLength = COM_WORDLENGTH_8B;
  com.StopBits = COM_STOPBITS_1;
  com.Parity = COM_PARITY_NONE;
  com.HwFlowCtl = COM_HWCONTROL_NONE;
  if (BSP_COM_Init(COM1, &com) != BSP_ERROR_NONE) Error_Handler();

  MicLine("N6MIC_READY,1,16000,1,16,80000\n");

  while (1)
  {
    uint8_t command;
    HAL_StatusTypeDef status = HAL_UART_Receive(&hcom_uart[COM1], &command, 1U, 100U);
    if (status == HAL_OK)
    {
      if (command == '?') MicLine("N6MIC_READY,1,16000,1,16,80000\n");
      else if (command == 'R') MicRecord();
    }
    else if (status != HAL_TIMEOUT)
      __HAL_UART_CLEAR_OREFLAG(&hcom_uart[COM1]);
  }
}

/* USER CODE BEGIN CLK 1 */
/* USER CODE END CLK 1 */

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the System Power Supply
  */
  if (HAL_PWREx_ConfigSupply(PWR_EXTERNAL_SOURCE_SUPPLY) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /* Enable HSI */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSIDiv = RCC_HSI_DIV1;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Get current CPU/System buses clocks configuration and if necessary switch
 to intermediate HSI clock to ensure target clock can be set
  */
  HAL_RCC_GetClockConfig(&RCC_ClkInitStruct);
  if ((RCC_ClkInitStruct.CPUCLKSource == RCC_CPUCLKSOURCE_IC1) ||
     (RCC_ClkInitStruct.SYSCLKSource == RCC_SYSCLKSOURCE_IC2_IC6_IC11))
  {
    RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_CPUCLK | RCC_CLOCKTYPE_SYSCLK);
    RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_HSI;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct) != HAL_OK)
    {
      /* Initialization Error */
      Error_Handler();
    }
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_NONE;
  RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL1.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL1.PLLM = 4;
  RCC_OscInitStruct.PLL1.PLLN = 75;
  RCC_OscInitStruct.PLL1.PLLFractional = 0;
  RCC_OscInitStruct.PLL1.PLLP1 = 1;
  RCC_OscInitStruct.PLL1.PLLP2 = 1;
  RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL3.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL3.PLLM = 8;
  RCC_OscInitStruct.PLL3.PLLN = 172;
  RCC_OscInitStruct.PLL3.PLLFractional = 0;
  RCC_OscInitStruct.PLL3.PLLP1 = 7;
  RCC_OscInitStruct.PLL3.PLLP2 = 4;
  RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_CPUCLK|RCC_CLOCKTYPE_HCLK
                              |RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1
                              |RCC_CLOCKTYPE_PCLK2|RCC_CLOCKTYPE_PCLK5
                              |RCC_CLOCKTYPE_PCLK4;
  RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_IC1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_IC2_IC6_IC11;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_APB1_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_APB2_DIV1;
  RCC_ClkInitStruct.APB4CLKDivider = RCC_APB4_DIV1;
  RCC_ClkInitStruct.APB5CLKDivider = RCC_APB5_DIV1;
  RCC_ClkInitStruct.IC1Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC1Selection.ClockDivider = 2;
  RCC_ClkInitStruct.IC2Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC2Selection.ClockDivider = 3;
  RCC_ClkInitStruct.IC6Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC6Selection.ClockDivider = 4;
  RCC_ClkInitStruct.IC11Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC11Selection.ClockDivider = 3;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief GPDMA1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPDMA1_Init(void)
{

  /* USER CODE BEGIN GPDMA1_Init 0 */

  /* USER CODE END GPDMA1_Init 0 */

  /* Peripheral clock enable */
  __HAL_RCC_GPDMA1_CLK_ENABLE();

  /* GPDMA1 interrupt Init */
    HAL_NVIC_SetPriority(GPDMA1_Channel6_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(GPDMA1_Channel6_IRQn);

  /* USER CODE BEGIN GPDMA1_Init 1 */

  /* USER CODE END GPDMA1_Init 1 */
  /* USER CODE BEGIN GPDMA1_Init 2 */

  /* USER CODE END GPDMA1_Init 2 */

}

/**
  * @brief MDF1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_MDF1_Init(void)
{

  /* USER CODE BEGIN MDF1_Init 0 */

  /* USER CODE END MDF1_Init 0 */

  /* USER CODE BEGIN MDF1_Init 1 */

  /* USER CODE END MDF1_Init 1 */

  /**
    MdfHandle0 structure initialization and HAL_MDF_Init function call
  */
  MdfHandle0.Instance = MDF1_Filter0;
  MdfHandle0.Init.CommonParam.InterleavedFilters = 0;
  MdfHandle0.Init.CommonParam.ProcClockDivider = 2;
  MdfHandle0.Init.CommonParam.OutputClock.Activation = ENABLE;
  MdfHandle0.Init.CommonParam.OutputClock.Pins = MDF_OUTPUT_CLOCK_0;
  MdfHandle0.Init.CommonParam.OutputClock.Divider = 12;
  MdfHandle0.Init.CommonParam.OutputClock.Trigger.Activation = DISABLE;
  MdfHandle0.Init.SerialInterface.Activation = ENABLE;
  MdfHandle0.Init.SerialInterface.Mode = MDF_SITF_NORMAL_SPI_MODE;
  MdfHandle0.Init.SerialInterface.ClockSource = MDF_SITF_CCK0_SOURCE;
  MdfHandle0.Init.SerialInterface.Threshold = 31;
  MdfHandle0.Init.FilterBistream = MDF_BITSTREAM0_FALLING;
  if (HAL_MDF_Init(&MdfHandle0) != HAL_OK)
  {
    Error_Handler();
  }

  /**
    MdfFilterConfig0, MdfOldConfig0 and/or MdfScdConfig0 structures initialization

    WARNING : only structures are filled, no specific init function call for filter
  */
  MdfFilterConfig0.DataSource = MDF_DATA_SOURCE_BSMX;
  MdfFilterConfig0.Delay = 0;
  MdfFilterConfig0.CicMode = MDF_ONE_FILTER_SINC4;
  MdfFilterConfig0.DecimationRatio = 32;
  MdfFilterConfig0.Offset = 0;
  MdfFilterConfig0.Gain = 14;
  MdfFilterConfig0.ReshapeFilter.Activation = ENABLE;
  MdfFilterConfig0.ReshapeFilter.DecimationRatio = MDF_RSF_DECIMATION_RATIO_4;
  MdfFilterConfig0.HighPassFilter.Activation = ENABLE;
  MdfFilterConfig0.HighPassFilter.CutOffFrequency = MDF_HPF_CUTOFF_0_000625FPCM;
  MdfFilterConfig0.Integrator.Activation = DISABLE;
  MdfFilterConfig0.SoundActivity.Activation = DISABLE;
  MdfFilterConfig0.AcquisitionMode = MDF_MODE_ASYNC_CONT;
  MdfFilterConfig0.FifoThreshold = MDF_FIFO_THRESHOLD_NOT_EMPTY;
  MdfFilterConfig0.DiscardSamples = 0;
  /* USER CODE BEGIN MDF1_Init 2 */

  /* USER CODE END MDF1_Init 2 */

}

/**
  * @brief RIF Initialization Function
  * @param None
  * @retval None
  */
  static void SystemIsolation_Config(void)
{

  /* USER CODE BEGIN RIF_Init 0 */

  /* USER CODE END RIF_Init 0 */

  /* set all required IPs as secure privileged */
  __HAL_RCC_RIFSC_CLK_ENABLE();

  /* RIF-Aware IPs Config */

  /* set up GPDMA configuration */
  /* set GPDMA1 channel 6 used by MDF1 */
  if (HAL_DMA_ConfigChannelAttributes(&handle_GPDMA1_Channel6,DMA_CHANNEL_SEC|DMA_CHANNEL_PRIV|DMA_CHANNEL_SRC_SEC|DMA_CHANNEL_DEST_SEC)!= HAL_OK )
  {
    Error_Handler();
  }

  /* set up GPIO configuration */
  HAL_GPIO_ConfigPinAttributes(GPIOE,GPIO_PIN_2,GPIO_PIN_SEC|GPIO_PIN_NPRIV);
  HAL_GPIO_ConfigPinAttributes(GPIOE,GPIO_PIN_8,GPIO_PIN_SEC|GPIO_PIN_NPRIV);

  /* USER CODE BEGIN RIF_Init 1 */

  /* USER CODE END RIF_Init 1 */
  /* USER CODE BEGIN RIF_Init 2 */

  /* USER CODE END RIF_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* USER CODE BEGIN MX_GPIO_Init_1 */
  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOE_CLK_ENABLE();

  /* USER CODE BEGIN MX_GPIO_Init_2 */
  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
void MPU_Config(void)
{
  MPU_Region_InitTypeDef default_config = {0};
  MPU_Attributes_InitTypeDef attr_config = {0};
  uint32_t primask_bit = __get_PRIMASK();
  __disable_irq();

  /* disable the MPU */
  HAL_MPU_Disable();

  /* create an attribute configuration for the MPU */
  attr_config.Attributes = INNER_OUTER(MPU_NOT_CACHEABLE);
  attr_config.Number = MPU_ATTRIBUTES_NUMBER0;

  HAL_MPU_ConfigMemoryAttributes(&attr_config);

  /* Create a non cacheable region */
  /*Normal memory type, code execution allowed */
  default_config.Enable = MPU_REGION_ENABLE;
  default_config.Number = MPU_REGION_NUMBER0;
  default_config.BaseAddress = __NON_CACHEABLE_SECTION_BEGIN;
  default_config.LimitAddress = __NON_CACHEABLE_SECTION_END;
  default_config.DisableExec = MPU_INSTRUCTION_ACCESS_ENABLE;
  default_config.AccessPermission = MPU_REGION_ALL_RW;
  default_config.IsShareable = MPU_ACCESS_NOT_SHAREABLE;
  default_config.AttributesIndex = MPU_ATTRIBUTES_NUMBER0;
  HAL_MPU_ConfigRegion(&default_config);

  /* enable the MPU */
  HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);

  /* Exit critical section to lock the system and avoid any issue around MPU mechanisme */
  __set_PRIMASK(primask_bit);
}

/**
  * @brief  Probe the WM8904 audio codec.
  * @param  None
  * @retval None
  */
static void WM8904_Probe(void)
{
  WM8904_IO_t              IOCtx;
  uint32_t                 wm8904_id;
  static WM8904_Object_t   WM8904Obj;

  /* Configure the audio driver */
  IOCtx.Address     = 0x34U;
  IOCtx.Init        = BSP_I2C2_Init;
  IOCtx.DeInit      = BSP_I2C2_DeInit;
  IOCtx.ReadReg     = BSP_I2C2_ReadReg;
  IOCtx.WriteReg    = BSP_I2C2_WriteReg;
  IOCtx.GetTick     = BSP_GetTick;

  if (WM8904_RegisterBusIO(&WM8904Obj, &IOCtx) != WM8904_OK)
  {
    Error_Handler();
  }
  else if (WM8904_ReadID(&WM8904Obj, &wm8904_id) != WM8904_OK)
  {
    Error_Handler();
  }
  else if ((wm8904_id & WM8904_ID_MASK) != WM8904_ID)
  {
    Error_Handler();
  }
  else
  {
    Audio_Drv = (AUDIO_Drv_t *) &WM8904_Driver;
    Audio_CompObj = &WM8904Obj;
  }
}

/**
  * @brief SAI1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_SAI1_Init(void)
{

  /* USER CODE BEGIN SAI1_Init 0 */

  /* USER CODE END SAI1_Init 0 */

  /* USER CODE BEGIN SAI1_Init 1 */

  /* USER CODE END SAI1_Init 1 */
  hsai_BlockA1.Instance = SAI1_Block_A;
  hsai_BlockA1.Init.Protocol = SAI_FREE_PROTOCOL;
  hsai_BlockA1.Init.AudioMode = SAI_MODEMASTER_TX;
  hsai_BlockA1.Init.DataSize = SAI_DATASIZE_16;
  hsai_BlockA1.Init.FirstBit = SAI_FIRSTBIT_MSB;
  hsai_BlockA1.Init.ClockStrobing = SAI_CLOCKSTROBING_FALLINGEDGE;
  hsai_BlockA1.Init.Synchro = SAI_ASYNCHRONOUS;
  hsai_BlockA1.Init.OutputDrive = SAI_OUTPUTDRIVE_ENABLE;
  hsai_BlockA1.Init.NoDivider = SAI_MASTERDIVIDER_ENABLE;
  hsai_BlockA1.Init.FIFOThreshold = SAI_FIFOTHRESHOLD_1QF;
  hsai_BlockA1.Init.AudioFrequency = SAI_AUDIO_FREQUENCY_16K;
  hsai_BlockA1.Init.SynchroExt = SAI_SYNCEXT_DISABLE;
  hsai_BlockA1.Init.MckOutput = SAI_MCK_OUTPUT_ENABLE;
  hsai_BlockA1.Init.MonoStereoMode = SAI_MONOMODE;
  hsai_BlockA1.Init.CompandingMode = SAI_NOCOMPANDING;
  hsai_BlockA1.Init.TriState = SAI_OUTPUT_NOTRELEASED;
  hsai_BlockA1.Init.PdmInit.Activation = DISABLE;
  hsai_BlockA1.FrameInit.FrameLength = 32;
  hsai_BlockA1.FrameInit.ActiveFrameLength = 16;
  hsai_BlockA1.FrameInit.FSDefinition = SAI_FS_CHANNEL_IDENTIFICATION;
  hsai_BlockA1.FrameInit.FSPolarity = SAI_FS_ACTIVE_LOW;
  hsai_BlockA1.FrameInit.FSOffset = SAI_FS_BEFOREFIRSTBIT;
  hsai_BlockA1.SlotInit.FirstBitOffset = 0;
  hsai_BlockA1.SlotInit.SlotSize = SAI_SLOTSIZE_16B;
  hsai_BlockA1.SlotInit.SlotNumber = 2;
  hsai_BlockA1.SlotInit.SlotActive = SAI_SLOTACTIVE_0 | SAI_SLOTACTIVE_1;
  if (HAL_SAI_Init(&hsai_BlockA1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN SAI1_Init 2 */

  /* USER CODE END SAI1_Init 2 */

}

/**
  * @brief  Playback initialization
  * @param  None
  * @retval None
  */
static void Playback_Init(void)
{
  /* Probe the audio codec */
  WM8904_Probe();

  /* Initialize SAI peripheral */
  MX_SAI1_Init();

  /* Initialize audio codec */
  WM8904_Init_t codec_init;
  codec_init.InputDevice  = WM8904_IN_NONE;
  codec_init.OutputDevice = WM8904_OUT_HEADPHONE;
  codec_init.Resolution   = WM8904_RESOLUTION_16B;
  codec_init.Frequency    = WM8904_FREQUENCY_16K;
  codec_init.Volume       = 80U;
  if (Audio_Drv->Init(Audio_CompObj, &codec_init) < 0)
  {
    Error_Handler();
  }
  if (Audio_Drv->Play(Audio_CompObj) != 0)
  {
    Error_Handler();
  }
}

/**
  * @brief  MDF acquisition complete callback.
  * @param  hmdf MDF handle.
  * @retval None.
  */
void HAL_MDF_AcqCpltCallback(MDF_HandleTypeDef *hmdf)
{
  if (hmdf == &MdfHandle0) MicCopy(&PcmBuffer[1024]);
}

/**
  * @brief  MDF acquisition half complete callback.
  * @param  hmdf MDF handle.
  * @retval None.
  */
void HAL_MDF_AcqHalfCpltCallback(MDF_HandleTypeDef *hmdf)
{
  if (hmdf == &MdfHandle0) MicCopy(&PcmBuffer[0]);
}
void HAL_MDF_ErrorCallback(MDF_HandleTypeDef *hmdf)
{
  /* 飽和交由電腦統計；其他 MDF/DMA 錯誤才中止錄音。 */
  if (hmdf == &MdfHandle0 &&
      (hmdf->ErrorCode & ~MDF_ERROR_SATURATION) != MDF_ERROR_NONE)
  {
    MicFailed = 1U;
    MicActive = 0U;
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  while (1)
  {
    /* Toggle red led for error */
    (void) BSP_LED_Toggle(LED_RED);
    HAL_Delay(500);
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
