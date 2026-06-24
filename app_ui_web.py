import json
import os
import re
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
MODEL_PATH = BASE_DIR / os.getenv("MODEL_PATH", "best.pt")
MAPPING_PATH = BASE_DIR / os.getenv("PILL_MAPPING_PATH", "pill_mapping.json")


@st.cache_resource
def load_yolo_model():
    if not MODEL_PATH.exists():
        return None
    return YOLO(str(MODEL_PATH))


@st.cache_data
def load_pill_mapping():
    if not MAPPING_PATH.exists():
        return {}

    with MAPPING_PATH.open("r", encoding="utf-8") as mapping_file:
        return json.load(mapping_file)


def clean_text(value):
    if not value:
        return "제공된 정보가 없습니다."
    return re.sub(r"</?doc>", "", str(value)).strip()


def predict_pills(model, image):
    results = model.predict(source=image, conf=0.5, verbose=False)
    predictions_by_label = {}

    for result in results:
        # 객체 탐지 모델
        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                confidence = float(box.conf[0])

                previous = predictions_by_label.get(label)
                if previous is None or confidence > previous["confidence"]:
                    predictions_by_label[label] = {
                        "label": label,
                        "confidence": confidence,
                    }

        # 이미지 분류 모델
        elif result.probs is not None:
            class_id = int(result.probs.top1)
            label = model.names[class_id]
            predictions_by_label[label] = {
                "label": label,
                "confidence": float(result.probs.top1conf),
            }

    return sorted(
        predictions_by_label.values(),
        key=lambda prediction: prediction["confidence"],
        reverse=True,
    )


def get_pill_info(mapping):
    item_seq = str(mapping.get("item_seq", "")).strip()
    item_name = str(mapping.get("item_name", "")).strip()

    if item_seq:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/pill/detail/{item_seq}",
            timeout=15,
        )
    elif item_name:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/pill/search",
            params={"name": item_name, "num_of_rows": 1},
            timeout=15,
        )
    else:
        return None

    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return data[0] if data else None
    return data


def get_dur_warning(item_seq, warning_type):
    response = requests.get(
        f"{BACKEND_URL}/api/v1/dur/{warning_type}/{item_seq}",
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_interactions(drug_names):
    response = requests.post(
        f"{BACKEND_URL}/api/v1/interaction-check",
        json=drug_names,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def display_interactions(drug_names):
    if len(drug_names) < 2:
        return

    st.subheader("병용금기 확인")

    try:
        result = get_interactions(drug_names)
    except requests.RequestException as error:
        st.warning(f"병용금기 정보를 조회하지 못했습니다: {error}")
        return

    warnings = result.get("warnings", [])
    if warnings:
        st.error("함께 복용할 때 주의가 필요한 조합이 발견되었습니다.")
        for warning in warnings:
            st.write(
                f"- {warning.get('drug_a', '')} + "
                f"{warning.get('drug_b', '')}: "
                f"{warning.get('description', '상세 정보 없음')}"
            )
    else:
        st.info(
            "조회된 병용금기 정보가 없습니다. "
            "모든 상황에서 안전하다는 의미는 아닙니다."
        )


def display_dur(item_seq):
    if not item_seq:
        return

    st.subheader("특수 복용 주의 정보")

    try:
        pregnant = get_dur_warning(item_seq, "pregnant")
        elderly = get_dur_warning(item_seq, "elderly")
    except requests.RequestException as error:
        st.warning(f"임부·연령별 주의 정보를 조회하지 못했습니다: {error}")
        return

    pregnant_column, elderly_column = st.columns(2)

    with pregnant_column:
        if pregnant.get("has_warning"):
            st.error("임부금기 정보가 있습니다.")
        else:
            st.info("조회된 임부금기 정보가 없습니다.")

    with elderly_column:
        if elderly.get("has_warning"):
            st.warning("연령별 주의 정보가 있습니다.")
        else:
            st.info("조회된 연령별 주의 정보가 없습니다.")


def display_pill_info(pill):
    st.subheader(pill.get("item_name", "의약품 정보"))

    if pill.get("entp_name"):
        st.caption(f"제조·수입사: {pill['entp_name']}")

    st.markdown("#### 효능·효과")
    st.info(clean_text(pill.get("efficacy")))

    st.markdown("#### 복용 방법과 용량")
    st.success(clean_text(pill.get("usage")))

    st.markdown("#### 복용 시 주의사항")
    st.error(clean_text(pill.get("caution")))

    st.caption(
        "이 정보는 참고용입니다. 실제 복용 전 의사 또는 약사와 상담하세요."
    )


st.set_page_config(
    page_title="의약품 안전 식별 시스템",
    page_icon="P",
    layout="centered",
)

st.title("의약품 안전 식별 시스템")
st.write(
    "알약 사진을 업로드하거나 촬영하면 AI가 알약을 식별하고 "
    "공식 의약품 정보를 조회합니다."
)

model = load_yolo_model()
mapping_by_label = load_pill_mapping()

upload_tab, camera_tab = st.tabs(["사진 업로드", "카메라 촬영"])

with upload_tab:
    uploaded_image = st.file_uploader(
        "알약 사진을 선택하세요.",
        type=["jpg", "jpeg", "png", "webp"],
    )

with camera_tab:
    camera_image = st.camera_input("알약이 중앙에 오도록 촬영하세요.")

selected_image = camera_image or uploaded_image

if selected_image is not None:
    image = Image.open(selected_image).convert("RGB")
    st.image(image, caption="분석할 사진", use_container_width=True)

    if st.button("알약 분석하기", type="primary", use_container_width=True):
        if model is None:
            st.error(f"모델 파일을 찾을 수 없습니다: {MODEL_PATH.name}")
            st.stop()

        with st.spinner("AI 모델이 알약을 분석하고 있습니다."):
            predictions = predict_pills(model, image)

        if not predictions:
            st.warning(
                "사진에서 알약을 인식하지 못했습니다. "
                "더 밝고 선명한 사진으로 다시 시도해 주세요."
            )
            st.stop()

        st.subheader("AI 식별 결과")

        resolved_pills = []
        official_names = []

        for prediction in predictions:
            label = prediction["label"]
            confidence = prediction["confidence"] * 100
            st.write(f"- {label}: {confidence:.1f}%")

            mapping = mapping_by_label.get(label)
            if mapping is None:
                st.warning(
                    f"모델 클래스 '{label}'이 pill_mapping.json에 없습니다."
                )
                continue

            try:
                pill = get_pill_info(mapping)
            except requests.RequestException as error:
                st.warning(f"'{label}'의 공식 정보를 조회하지 못했습니다: {error}")
                continue

            if pill is None:
                st.warning(f"'{label}'에 연결된 공공데이터 결과가 없습니다.")
                continue

            resolved_pills.append(pill)
            official_names.append(pill.get("item_name", mapping["item_name"]))

        display_interactions(official_names)

        if resolved_pills:
            main_pill = resolved_pills[0]
            st.divider()
            display_dur(main_pill.get("item_seq", ""))
            display_pill_info(main_pill)
        else:
            st.error(
                "모델 예측 결과를 공공데이터와 연결하지 못했습니다. "
                "pill_mapping.json을 확인해 주세요."
            )
