GPU version of https://ai.gitcode.com/ascend-tribe/openpangu-embedded-1b-model/tree/main

# 开源盘古 Embedded-1B
中文 | [English](README_EN.md)

## 1.简介

openPangu-Embedded-1B 是基于昇腾 NPU 从零训练的高效语言模型，参数量为 1B（不含词表Embedding），模型结构采用 26 层 Dense 架构，训练了约 10T tokens。通过昇腾 Atlas 200I A2可用的模型架构设计、数据和训练策略优化，openPangu-Embedded-1B 在保持端侧运行的要求下达到了较高的精度。

## 2. 模型架构

openPangu-Embedded-1B 是一个为端侧设备运行而设计的高效快思考语言模型，支持昇腾 Atlas 200I A2。


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



## 3. 测评结果

| 评测集 | 测评指标 | 快思考   |
|:---: |:---: |:---: |
| **通用能力** | |
| MMLU       |    Acc        | 60.72  |
| CMMLU     |     Acc        | 51.99  |
| C-Eval  | Acc  | 60.98  |
| IF-Eval | Prompt Strict | 56.56 |
| CLUEWSC | Acc | 68.55 |
| **数学&推理** | |
| GSM8K    |    Acc          | 66.72  |
| MATH-500     |   Acc        | 52.00  |
| DROP | F1 |  50.31 |
| **代码能力** | |
| MBPP       |      Pass@1      | 54.09  |
| HumanEval   |    Pass@1       | 56.71  |

**注：** 评测过程中system prompt 为空。


## 4. 部署和使用

### 4.1 环境准备

##### 硬件规格
Atlas 800T A2 (64GB)，驱动与固件安装包获取请参照 [[Atlas 800T A2](https://www.hiascend.com/hardware/firmware-drivers/community?product=4&model=26&cann=8.2.RC1.alpha003&driver=Ascend+HDK+25.0.RC1)]。

##### 软件环境

- 操作系统：Linux（推荐 openEuler>=24.03）
- CANN==8.1.RC1，安装准备及流程请参照 [CANN Install](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/82RC1alpha002/softwareinst/instg/instg_0001.html?Mode=PmIns&OS=Ubuntu&Software=cannToolKit)
- python==3.10
- torch==2.1.0
- torch-npu==2.1.0.post12
- transformers==4.53.2

以上软件配套经过验证，理论可以支持更高版本，如有疑问，可以提交 issue。

### 4.2 权重完整性校验

请参考以下方法对下载内容进行完整性校验，hash 值存储在 checklist.chk 文件中。

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
### 4.3 推理样例
下述内容提供 openPangu-Embedded-1B 在 `transformers` 框架上进行推理的一个简单示例：
>运行前请修改 generate.py，添加模型路径。
```bash
cd inference
python generate.py
```
同时，openPangu-Embedded-1B 模型推理已适配昇腾 MindIE 2.2.T10（将于近期发布），支持 OrangePi AIpro (昇腾 Atlas 200I A2) 推理部署。届时可前往 [昇腾社区ModelZoo](https://gitee.com/ascend/ModelZoo-PyTorch/blob/master/MindIE/LLM/Pangu/openPangu-Embedded-1B-OrangePi/README.md) 下载适配，下载镜像前需要申请权限，耐心等待权限申请通过后，根据指南下载对应版本文件和安装指导完成推理部署。

## 5. 模型许可证

除文件中对开源许可证另有约定外，openPangu-Embedded-1B 模型根据 OPENPANGU MODEL LICENSE AGREEMENT VERSION 1.0 授权，旨在允许使用并促进人工智能技术的进一步发展。有关详细信息，请参阅模型存储库根目录中的 [LICENSE](LICENSE) 文件。


## 6. 免责声明
由于 openPangu-Embedded-1B（“模型”）所依赖的技术固有的技术限制，以及人工智能生成的内容是由盘古自动生成的，华为无法对以下事项做出任何保证：
- 尽管该模型的输出由 AI 算法生成，但不能排除某些信息可能存在缺陷、不合理或引起不适的可能性，生成的内容不代表华为的态度或立场；
- 无法保证该模型 100% 准确、可靠、功能齐全、及时、安全、无错误、不间断、持续稳定或无任何故障；
- 该模型的输出内容不构成任何建议或决策，也不保证生成的内容的真实性、完整性、准确性、及时性、合法性、功能性或实用性。生成的内容不能替代医疗、法律等领域的专业人士回答您的问题。生成的内容仅供参考，不代表华为的任何态度、立场或观点。您需要根据实际情况做出独立判断，华为不承担任何责任。

## 7. 反馈

如果有任何意见和建议，请提交issue或联系 openPangu@huawei.com。