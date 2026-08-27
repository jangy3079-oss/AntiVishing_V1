"""
STT/자유텍스트 코칭탐지 로컬 분류기 학습 스크립트 (v5.1).

데이터 6종을 합쳐서 학습한다 (자세한 배경은 ml/README.md 참고):
1) KorCCViD_v1.3.csv - 정상 609 / 보이스피싱 121건 (실제 통화 전사)
   https://github.com/selfcontrol7/Korean_Voice_Phishing_Detection
2) df_data_vishing.csv - 같은 저장소의 추가 보이스피싱 전사(v1.3과 중복 제거 후 610건 신규)
   -> v1.3의 121건만으로는 각본 다양성이 부족해 "학습 각본과 조금만 달라도 못 잡는" 문제가
      있었음. 이 파일로 보이스피싱 표본을 731건까지 늘려서 해결했다.
3) AI-Hub "민원(콜센터) 질의-응답 데이터"의 금융보험 도메인 고객 발화 248건
   (data_prep/finance_normal_samples.json에 이미 추출/정제되어 포함됨)
   -> KorCCViD의 "정상" 표본이 전부 친구/가족 잡담이라 "이체/계좌" 같은 정상적인
      금융 어휘를 쓰는 대화가 아예 없었음. 은행 창구의 정상 송금 사유 설명까지
      보이스피싱으로 오분류하던 문제를 이 데이터로 해결했다.
4) data_prep/ambiguous_normal_synthetic.json (28건, Claude 합성, label=0)
   -> v4를 실사용 문장으로 검증하던 중 "급함/큰금액/제3자가 불러준 계좌"처럼 표면적으로
      사기 각본과 겹치는 정상 거래(부동산 계약금, 등록금, 거래처 대금, 대리 수령 등)를
      만들어 테스트했더니 16/16 전부 99%+ 확률로 오탐했다. 원인: 학습 데이터의 "정상"
      표본이 전부 차분한 발화뿐이라 "다급함" 자체를 보이스피싱 신호로 학습한 것으로
      보임. 이 문제를 겨냥해 만든 하드-네거티브 표본.
5) data_prep/family_impersonation_synthetic.json (21건, Claude 합성, label=1)
   -> 기존 학습 데이터가 전부 검찰/기관 사칭류 격식체 통화였고, 자녀/지인 사칭
      (발신번호 변조 납치·사고 빙자, 메신저 해킹 후 지인 사칭 문자체)은 구조적으로
      없었다. 실제로 v4에 테스트해보니 문자체·반말 지인사칭 6건 중 5건을 놓쳤다
      (prob_phishing < 1%). 이 유형을 겨냥해 만든 하드-포지티브 표본.
   두 합성 데이터셋은 실제 사기수법(금융감독원 공개 유형 설명) 기반으로 만들었지만
   실제 통화 전사가 아니라 Claude가 생성한 합성 데이터임을 명시한다. 학습 신호를
   충분히 주기 위해 3배 오버샘플링한다(OVERSAMPLE_SYNTH, 아래 참고).
6) data_prep/coaching_inprogress_synthetic.json (16건, Claude 합성, label=1, v5.1 추가)
   -> v5를 테스트하던 중 "지금 통화하면서 불러주는 대로 계좌번호 입력하고 있어요"
      (v4에서 92.2%로 정탐) 같은 짧은 코칭탐지 문장들이 v5에서 전부 0.1~2.8%로
      붕괴하는 회귀를 발견했다. 원인: (4)의 "애매한 정상" 표본이 전부 "급하게/
      계좌번호/불러주신" 같은 어휘를 쓰는 짧은 문장인데 이걸 3배 오버샘플링하니
      "이 어휘=정상"이라는 지름길을 모델이 배워버림. 같은 어휘를 쓰되 실제
      코칭/사기 문맥인 예시를 대칭으로 추가해 어휘가 아니라 문맥으로 구분하도록
      재균형했다.

실행 전 준비:
- KorCCViD_v1.3.csv, df_data_vishing.csv를 이 폴더(ml/)에 받아둘 것
  (df_data_vishing.csv: https://raw.githubusercontent.com/selfcontrol7/Korean_Voice_Phishing_Detection/main/Data_Collection_Preprocessing/df_data_vishing.csv)
- data_prep/finance_normal_samples.json, ambiguous_normal_synthetic.json,
  family_impersonation_synthetic.json, coaching_inprogress_synthetic.json은
  이미 저장소에 포함되어 있음(재추출 불필요)

실행: python train_coaching_classifier.py
CPU 4코어 기준 2 epoch 학습에 약 7~8분 소요.
"""
import json
import re

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import Dataset

MODEL_NAME = "klue/roberta-small"
MAX_LEN = 256
OUT_DIR = "../backend/app/models/coaching_classifier"
EPOCHS = 2
OVERSAMPLE_SYNTH = 3  # 합성 하드example 3종(4,5,6)을 이 배수만큼 반복해 학습 신호를 키운다


def clean_text(t: str) -> str:
    t = str(t)
    t = re.sub(r"[a-z]/", " ", t)  # 전사 표기 규칙(disfluency marker) 제거
    t = re.sub(r"[*+]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# 1) KorCCViD v1.3
df1 = pd.read_csv("KorCCViD_v1.3.csv").dropna(subset=["Transcript", "Label"]).reset_index(drop=True)
df1["text"] = df1["Transcript"].astype(str).apply(clean_text)
df1["label"] = df1["Label"].astype(int)
df1 = df1[["text", "label"]]

# 2) df_data_vishing.csv - v1.3과 중복 제거 후 신규 보이스피싱만 추가
vishing = pd.read_csv("df_data_vishing.csv")
vishing["text"] = vishing["transcript"].apply(clean_text)
vishing = vishing.drop_duplicates(subset="text")
known_phish_texts = set(df1[df1.label == 1]["text"])
new_phish = vishing[~vishing["text"].isin(known_phish_texts)]
new_phish = new_phish[new_phish["text"].str.len() >= 10]
df3 = pd.DataFrame({"text": new_phish["text"].tolist(), "label": 1})

# 3) AI-Hub 금융보험 정상 고객 발화
with open("data_prep/finance_normal_samples.json", encoding="utf-8") as f:
    fin_samples = json.load(f)
df2 = pd.DataFrame([{"text": r["text"], "label": 0} for r in fin_samples])

# 4) 애매한데 정상인 케이스 (Claude 합성, 하드-네거티브)
with open("data_prep/ambiguous_normal_synthetic.json", encoding="utf-8") as f:
    ambig_normal = json.load(f)
df4 = pd.DataFrame([{"text": r["text"], "label": 0, "synth": True} for r in ambig_normal])

# 5) 가족/지인 사칭 (Claude 합성, 하드-포지티브)
with open("data_prep/family_impersonation_synthetic.json", encoding="utf-8") as f:
    fam_imp = json.load(f)
df5 = pd.DataFrame([{"text": r["text"], "label": 1, "synth": True} for r in fam_imp])

# 6) 코칭 진행중 하드-포지티브 (v5.1, "급하게/계좌번호/불러주신" 어휘 충돌 완화용)
with open("data_prep/coaching_inprogress_synthetic.json", encoding="utf-8") as f:
    coaching_ip = json.load(f)
df6 = pd.DataFrame([{"text": r["text"], "label": 1, "synth": True} for r in coaching_ip])

for d in (df1, df2, df3):
    d["synth"] = False

df = pd.concat([df1, df2, df3, df4, df5, df6], ignore_index=True)
print(f"전체 {len(df)}건 (오버샘플링 전, 중복 없음), 정상={(df.label==0).sum()} 보이스피싱={(df.label==1).sum()}")

# 먼저 원본(1건당 1행)으로 split해서 val/test에 중복 유입(data leakage)을 막는다.
train_df, temp_df = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=42)
val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["label"], random_state=42)

# 오버샘플링은 train에만 적용 - 합성 하드example의 학습 신호를 키우되 val/test는 순수하게 유지.
synth_train = train_df[train_df["synth"]]
train_df = pd.concat([train_df] + [synth_train] * (OVERSAMPLE_SYNTH - 1), ignore_index=True)

print(f"train={len(train_df)}(합성 x{OVERSAMPLE_SYNTH} 반영) val={len(val_df)} test={len(test_df)}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


class TranscriptDataset(Dataset):
    def __init__(self, texts, labels):
        self.enc = tokenizer(list(texts), truncation=True, max_length=MAX_LEN, padding="max_length")
        self.labels = list(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.enc.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


train_ds = TranscriptDataset(train_df["text"], train_df["label"])
val_ds = TranscriptDataset(val_df["text"], val_df["label"])
test_ds = TranscriptDataset(test_df["text"], test_df["label"])

model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

# 정상:보이스피싱 비율이 이제 거의 1:1(857:731)에 가까워 큰 가중치가 필요 없지만,
# 약간의 잔여 불균형 보정을 위해 그대로 둔다.
n0, n1 = (train_df["label"] == 0).sum(), (train_df["label"] == 1).sum()
class_weights = torch.tensor([1.0, n0 / n1], dtype=torch.float32)
print("class_weights:", class_weights.tolist())


class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss_fct = torch.nn.CrossEntropyLoss(weight=class_weights.to(logits.device))
        loss = loss_fct(logits, labels)
        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    report = classification_report(labels, preds, output_dict=True, zero_division=0)
    return {
        "accuracy": report["accuracy"],
        "precision_1": report["1"]["precision"],
        "recall_1": report["1"]["recall"],
        "f1_1": report["1"]["f1-score"],
    }


args = TrainingArguments(
    output_dir="/tmp/coaching_classifier_train",
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    eval_strategy="epoch",
    save_strategy="no",
    logging_steps=20,
    learning_rate=2e-5,
    report_to=[],
    seed=42,
)

trainer = WeightedTrainer(
    model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=compute_metrics,
)

trainer.train()

print("\n=== held-out TEST 평가 ===")
pred = trainer.predict(test_ds)
preds = np.argmax(pred.predictions, axis=1)
print(classification_report(test_df["label"], preds, target_names=["정상", "보이스피싱"], zero_division=0))
print("confusion matrix (row=실제, col=예측):")
print(confusion_matrix(test_df["label"], preds))

model.save_pretrained(OUT_DIR)
tokenizer.save_pretrained(OUT_DIR)
print(f"\n모델 저장 완료: {OUT_DIR}")
