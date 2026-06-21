GPU version of https://ai.gitcode.com/ascend-tribe/openpangu-embedded-1b-model/tree/main

# **openPangu-Embedded-1B**

[中文](README.md) | English


## 1. Introduction

The openPangu-Embedded-1B is an efficient language model trained from scratch based on the Ascend NPU, with 1B parameters (excluding vocabulary embedding). The model employs a 26-layer dense architecture and was trained on approximately 10T tokens. Through  model architecture design for Ascend Atlas 200I A2, optimized data and training strategies, openPangu-Embedded-1B achieves high precision while meeting the requirements for edge-side deployment.

## 2. Model Architecture

The openPangu-Embedded-1B is a high-efficiency fast-thinking language model designed for operation on edge devices, with support for the Ascend Atlas 200I A2.


|                               |      openPangu-Embedded-1B      |
| :---------------------------: | :----------------: |
|       **Architecture**        |       Dense        |
|     **Parameters (Non-Embedding)**      |         1B         |
|     **Number of Layers**      |         26         |
|     **Hidden Dimension**      |        1536        |
|    **Attention Mechanism**    |     GQA      |
| **Number of Attention Heads** | 12 for Q, 6 for KV |
|      **Vocabulary Size**      |        153k        |
|      **Context Length (Natively)**       |        32k         |
|    **Training Tokens**        |      10T         |



## 3. Results

| Benchmark     | Metric         | Non-thinking   |
|:------------------:|:----------:|:--------:|
| **General** | |
| MMLU       |    Acc        | 60.72  |
| CMMLU     |     Acc        | 51.99  |
| C-Eval  | Acc  | 60.98  |
| IFEval | Prompt Strict | 56.56 |
| CLUEWSC | Acc | 68.55 |
| **Math & Reasoning** | |
| GSM8K    |    Acc          | 66.72  |
| MATH-500     |  Acc        | 52.00  |
| DROP | F1 |  50.31 |
| **Coding** | |
| MBPP       |      Pass@1      | 54.09  |
| HumanEval   |    Pass@1       | 56.71  |

**Note:** The system prompt is left empty.


## 4. Deployment

### 4.1 Environment

##### Hardware Requirements

Atlas 800T A2 (64GB), please refer to [[Atlas 800T A2](https://www.hiascend.com/hardware/firmware-drivers/community?product=4&model=26&cann=8.2.RC1.alpha003&driver=Ascend+HDK+25.0.RC1)] for obtaining the driver and firmware installation packages.

#### System Requirements & Dependencies

- System: Linux (OpenEuler ≥ 24.03 recommended)
- CANN==8.1.RC1: [CANN Install](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/82RC1alpha002/softwareinst/instg/instg_0001.html?Mode=PmIns&OS=Ubuntu&Software=cannToolKit)
- python==3.10
- torch==2.1.0
- torch-npu==2.1.0.post12
- transformers==4.53.2

The above software environment has been verified, and theoretically supports newer versions. For any questions, please submit an issue.

### 4.2 Integrity Check

Please refer to the following methods to verify the integrity of the downloaded content. The hash values are stored in the `checklist.chk` file.

```
#!/usr/bin/env bash
ARCH=$(uname -m)
MODEL_PATH="${TARGET_FOLDER}/${MODEL_FOLDER_PATH}"
cd "$MODEL_PATH" || exit 1
if [ "$ARCH" = "arm64" ]; then
    sha256sum checklist.chk
else
    sha256sum -c checklist.chk
fi
```

### 4.3 Inference Examples
The following provides a simple inference example of openPangu-Embedded-1B based on the `transformers` framework: 
>Please modify generate.py and add the model path before running.
```bash
cd inference
python generate.py
```
The openPangu-Embedded-1B model inference has been adapted for Ascend MindIE version 2.2.T10 (to be released soon), and can be deployed on OrangePi AIpro (Ascend Atlas 200I A2) for inference. The adapted package will be available for download on [Ascend Community ModelZoo](https://gitee.com/ascend/ModelZoo-PyTorch/blob/master/MindIE/LLM/Pangu/openPangu-Embedded-1B-OrangePi/README.md). Before downloading the image, you need to apply for permissions. Please wait patiently until the permission application is approved, then follow the guidelines to download the corresponding image file and installation guide to complete the inference deployment.

## 5. Model License

Unless otherwise noted, openPangu-Embedded-1B model is licensed under the terms and conditions of OPENPANGU MODEL LICENSE AGREEMENT VERSION 1.0, which is intended to be used permissively and enable the further development of artificial intelligence technologies. Please refer to the [LICENSE](LICENSE) file located in the root directory of the model repository for details.

## 6. Disclaimer

Due to the technical limitations inherent in the technology on which the  openPangu-Embedded-1B (“Model”) relies and the fact that the artificial intelligence generated content is automatically produced by Model, Huawei cannot make any guarantees regarding the following matters:
- The output of this Model is automatically generated via AI algorithms, it does not rule out the possibility that some of the information may be flawed, unreasonable, or cause discomfort, and the generated content does not represent Huawei's attitude or standpoint;
- There is no guarantee that this Model is 100% accurate, reliable, functional, timely, secure and safety, error-free, uninterrupted, continuously stable, or free of any faults;
- The output of this Model does not constitute any advices or decisions for you, and it does not guarantee the authenticity, completeness, accuracy, timeliness, legality, functionality, or practicality of the generated content. The generated content cannot replace professionals in medical, legal, and other fields in answering your questions. The generated content is for your reference only and does not represent any attitude, standpoint, or position of Huawei. You need to make independent judgments based on your actual situation, and Huawei does not assume any responsibilities.


## 7. Contact Us
If you have any comments or suggestions, please submit an issue or contact openPangu@huawei.com.