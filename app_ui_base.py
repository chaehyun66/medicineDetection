import streamlit as st
import requests
from PIL import Image
from ultralytics import YOLO
import os
import json 
from pathlib import Path
from dotenv import load_dotenv

st.set_page_config(
    page_title="스마트 의약품 종합 식별 시스템",
    page_icon="P",
    layout="centered"
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

MODEL_PATH = BASE_DIR / os.getenv(
    "MODEL_PATH",
    "best.pt"
)

MAPPING_PATH = BASE_DIR / os.getenv(
    "PILL_MAPPING_PATH",
    "pill_mapping.json"
)

MANUAL_INFO_PATH = BASE_DIR / os.getenv(
    "MANUAL_INFO_PATH",
    "pill_manual_info.json"
)

# ==================== [환경 설정 및 모델 로드] ====================


@st.cache_resource
def load_yolo_model():
    if os.path.exists(MODEL_PATH):
        return YOLO(MODEL_PATH)
    return None

model = load_yolo_model()

@st.cache_data
def load_pill_mapping():
    if not MAPPING_PATH.exists():
        return {}
    
    with open(MAPPING_PATH, "r", encoding="utf-8") as file:
        return json.load(file)
    
PILL_MAPPING = load_pill_mapping()

@st.cache_data
def load_manual_info():
    if not MANUAL_INFO_PATH.exists():
        return {}

    with MANUAL_INFO_PATH.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


MANUAL_INFO = load_manual_info()

# ==================== [팀원 FastAPI 서버 연동 함수들] ====================
def search_pill_from_server(drug_name):
    """1. 팀원 서버에 약 이름으로 상세 정보를 검색 요청하는 함수"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/pill/search", params={"name": drug_name, "num_of_rows": 1}, timeout=5)
        if response.status_code == 200 and response.json():
            return response.json()[0] # 검색된 첫 번째 약 정보 리턴
        return None
    except Exception:
        return None

def get_pill_detail_from_server(item_seq):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/pill/detail/{item_seq}",
            timeout=15
        )

        response.raise_for_status()

        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json(),
            "message": ""
        }

    except requests.HTTPError as error:
        return {
            "success": False,
            "status_code": error.response.status_code,
            "data": None,
            "message": f"의약품 정보 조회 실패: {error}"
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "status_code": None,
            "data": None,
            "message": f"서버 연결 실패: {error}"
        }
    
def get_mapped_pill_info(model_label):
    mapping = PILL_MAPPING.get(model_label)

    if mapping is None:
        return None, (
            f"모델 클래스 '{model_label}'이 "
            "pill_mapping.json에 없습니다."
        )

    item_seq = str(mapping.get("item_seq", "")).strip()
    item_name = str(mapping.get("item_name", "")).strip()

    if item_seq:
        result = get_pill_detail_from_server(item_seq)

        if result["success"]:
            return result["data"], None

        # e약은요에 등록되지 않은 경우 수동 정보 사용
        if result["status_code"] == 404:
            manual_data = MANUAL_INFO.get(model_label)

            if manual_data:
                return manual_data, None

            return None, (
                f"'{item_name}'은 e약은요에서 조회되지 않습니다. "
                "pill_manual_info.json에 공식 정보를 등록해 주세요."
            )

        return None, result["message"]

    if item_name:
        pill_data = search_pill_from_server(item_name)

        if pill_data:
            return pill_data, None
        
        if pill_data.get("source"):
            st.caption(f"정보 출처: {pill_data['source']}")

        manual_data = MANUAL_INFO.get(model_label)

        if manual_data:
            return manual_data, None

    return None, (
        f"'{model_label}'에 대한 의약품 정보를 찾지 못했습니다."
    )

def check_dur_warnings(item_seq, warning_type="pregnant"):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/dur/{warning_type}/{item_seq}",
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        data["success"] = True
        return data

    except requests.RequestException as error:
        return {
            "success": False,
            "has_warning": None,
            "warnings": [],
            "message": f"주의정보 조회 실패: {error}"
        }

def check_together_interaction(drug_names):
    """3. 사진에서 검출된 알약들이 서로 같이 먹으면 안 되는 병용금기 약물인지 체크하는 함수"""
    try:
        response = requests.post(f"{BACKEND_URL}/api/v1/interaction-check", json=drug_names, timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"is_safe": True, "warnings": []}
    except Exception:
        return {"is_safe": True, "warnings": []}
    
def check_together_interaction_safe(drug_names):
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/interaction-check",
            json=drug_names,
            timeout=30
        )

        response.raise_for_status()

        return {
            "success": True,
            "warnings": response.json().get("warnings", []),
            "message": ""
        }

    except requests.Timeout:
        return {
            "success": False,
            "warnings": [],
            "message": "병용금기 API 응답 시간이 초과됐습니다."
        }

    except requests.ConnectionError:
        return {
            "success": False,
            "warnings": [],
            "message": "FastAPI 서버에 연결할 수 없습니다."
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "warnings": [],
            "message": f"병용금기 조회에 실패했습니다: {error}"
        }

# ==================== [웹 화면 UI 구성] ====================

st.title("의약품 안전 식별 시스템")
st.write("알약 사진을 업로드하면 AI 분석 및 실시간 DUR(병용금기/임부·노인 금기) 검증을 수행합니다.")
st.markdown("---")

# 사진 업로드 기능
st.subheader("알약 사진 업로드")
upload_tab, camera_tab = st.tabs([
    "사진 업로드",
    "카메라 촬영"
])

uploaded_file = None

with upload_tab:
    uploaded_file = st.file_uploader(
        "알약 사진을 선택하세요",
        type=["jpg", "jpeg", "png", "webp"]
    )

with camera_tab:
    camera_file = st.camera_input(
        "알약이 중앙에 오도록 촬영하세요"
    )

if camera_file is not None:
    uploaded_file = camera_file

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.image(image, caption="업로드된 알약 사진", use_container_width=True)
        
    with col2:
        st.info("알약을 분석하는 중입니다...")
        
        if model is None:
            st.error(f"폴더 내에 학습된 모델 파일('{MODEL_PATH}')을 찾을 수 없습니다.")
        else:
            # ------------------ [YOLOv8 이미지 분석 처리] ------------------
            results = model.predict(source=image, conf=0.5)
            detected_pills = []
            
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    pill_name = model.names[class_id]
                    if pill_name not in detected_pills:
                        detected_pills.append(pill_name)
            
            # ------------------ [결과 확인 및 대시보드 출력] ------------------
            if not detected_pills:
                st.warning("사진에서 인식된 알약이 없습니다. 더 선명한 사진을 사용해 주세요.")
            else:
                st.success(f"**AI 식별 결과:** {', '.join(detected_pills)}")
                
                # 🔥 [기능 1: 병용금기 체크] 인식된 알약이 2개 이상일 때 실시간 상호작용 체크!
                official_drug_names = []
                
                for model_label in detected_pills:
                    mapping = PILL_MAPPING.get(model_label)
                    
                    if mapping is None:
                        st.warning(
                            f"'{model_label}' 클래스가 "
                            "pill_mapping.json에 없습니다."
                        )
                        continue
                    
                    item_name = mapping.get("item_name", "").strip()
                    
                    if item_name:
                        official_drug_names.append(item_name)
                
                if len(official_drug_names) >= 2:
                    with st.spinner("검출된 알약 간의 병용금기(DUR) 상호작용 검증 중..."):
                        interaction_data = check_together_interaction_safe(official_drug_names)
                        
                    if not interaction_data["success"]:
                        st.warning(interaction_data["message"])
                        
                    elif interaction_data["warnings"]:
                        st.error("병용금기 위험이 발견되었습니다.")
                        for warning in interaction_data["warnings"]:
                            st.write(f"- **{warning['drug_a']}** + **{warning['drug_b']}** + **{warning['description']}")
                    else:
                        st.info("**[DUR 안전]** 검출된 알약 간의 병용금기 위험이 없습니다.")
                
                # 가장 먼저 주가 되는 첫 번째 알약을 기준으로 상세 가이드 출력
                target_pill = detected_pills[0]
                
                with st.spinner("서버를 통해 식약처 공식 정보 요청 중..."):
                    pill_data, mapping_error = get_mapped_pill_info(target_pill)
                
                if mapping_error:
                    st.warning(mapping_error)
                
                if pill_data is not None:
                    st.success("의약품 정보 조회가 완료되었습니다.")
                    
                    # 데이터 매칭 확인용 품목기준코드
                    item_seq = pill_data.get("item_seq", "")
                    
                    # ------------------ [화면 메인 출력창] ------------------
                    st.markdown(f"### 공식 의약품명: **{pill_data.get('item_name', '정보 없음')}**")
                    if pill_data.get('entp_name'):
                        st.caption(f"제조/수입사: {pill_data.get('entp_name')}")
                    
                    # [기능 2: 임부금기 및 노인주의 실시간 특수 경고등 디스플레이]
                    if item_seq:
                        preg_result = check_dur_warnings(item_seq, "pregnant")
                        elder_result = check_dur_warnings(item_seq, "elderly")
                        
                        dur_col1, dur_col2 = st.columns(2)
                        with dur_col1:
                            if not preg_result.get("success"):
                                st.warning("임부금기 정보를 확인하지 못했습니다.")
                            elif preg_result.get("has_warning"):
                                st.error("**주의 약물** 임부금기 정보가 있습니다.")
                            else:
                                st.info("조회된 임부금기 정보가 없습니다.")

                        with dur_col2:
                            if not elder_result.get("success"):
                                st.warning("연령별 주의정보를 확인하지 못했습니다.")
                            elif elder_result.get("has_warning"):
                                st.warning("**주의 약물** 연령별 주의정보가 있습니다.")
                            else:
                                st.info("조회된 연령별 주의정보가 없습니다.")
                    
                    st.markdown("---")
                    
                    # 1. 언제 복용해야 하는지 (효능/효과)
                    st.markdown("#### 1. 효능 및 목적")
                    if pill_data.get('efficacy'):
                        st.info(pill_data['efficacy'].replace("<doc>", "").replace("</doc>", ""))
                    else:
                        st.write("제공된 정보가 없습니다.")
                        
                    # 2. 어떻게 복용하는지 (복용방법)
                    st.markdown("#### ⚙️ 2. 어떻게 복용하나요? (복용방법 및 용량)")
                    if pill_data.get('usage'):
                        st.success(pill_data['usage'].replace("<doc>", "").replace("</doc>", ""))
                    else:
                        st.write("제공된 정보가 없습니다.")
                        
                    # 3. 복용 시 주의사항
                    st.markdown("#### ⚠️ 3. 복용 시 주의사항")
                    if pill_data.get('caution'):
                        st.error(pill_data['caution'].replace("<doc>", "").replace("</doc>", ""))
                    else:
                        st.write("제공된 정보가 없습니다.")
                        
                else:
                    st.error(f"❌ '{target_pill}'에 대한 상세 정보를 조회할 수 없습니다.")
                    st.warning("💡 팀원의 백엔드 서버가 정상적으로 켜져 있는지(Port 8000), 그리고 서버 코드 내부의 `API_KEY`가 올바르게 작동 중인지 팀원과 확인해 보세요.")
