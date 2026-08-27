"""
STT/자유텍스트 코칭탐지 로컬 분류기 학습 스크립트 (v4).

데이터 3종을 합쳐서 학습한다 (자세한 배경은 ml/README.md 참고):
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

실행 전 준비:
- KorCCViD_v1.3.csv, df_data_vishing.csv를 이 폴더(ml/)에 받아둘 것
  (df_data_vishing.csv: https://raw.githubusercontent.com/selfcontrol7/Korean_Voice_Phishing_Detection/main/Data_Collection_Preprocessing/df_data_vishing.csv)
- data_prep/finance_normal_samples.json은 이미 저장소에 포함되어 있음(재추출 불필요)

실행: python train_coaching_classifier.py
CPU 4코어 기준 2 epoch 학습에 약 6~7분 소요.
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

df = pd.concat([df1, df2, df3], ignore_index=True)
print(f"전체 {len(df)}건, 정상={(df.label==0).sum()} 보이스피싱={(df.label==1).sum()}")

train_df, temp_df = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=42)
val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["label"], random_state=42)
print(f"train={len(train_df)} val={len(val_df)} test={len(test_df)}")

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
        loss_fct = torch.nn.CrossEntropyLoss(weight=class_weights)
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
