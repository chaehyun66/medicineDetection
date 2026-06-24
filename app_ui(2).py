import streamlit as st
import requests
from PIL import Image
from ultralytics import YOLO
import os

# ==================== [환경 설정 및 모델 로드] ====================
BACKEND_URL = "http://localhost:8000"

# 학습시킨 오픈소스 YOLOv8 모델 로드
MODEL_PATH = "best.pt" 

@st.cache_resource
def load_yolo_model():
    if os.path.exists(MODEL_PATH):
        return YOLO(MODEL_PATH)
    return None

model = load_yolo_model()

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

def check_dur_warnings(item_seq, warning_type="pregnant"):
    """2. 임부금기 및 노인주의(특정연령대금기)를 조회"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/dur/{warning_type}/{item_seq}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"has_warning": False, "warnings": []}
    except Exception:
        return {"has_warning": False, "warnings": []}

def check_together_interaction(drug_names):
    """3. 사진에서 검출된 알약들이 서로 같이 먹으면 안 되는 병용금기 약물인지 체크하는 함수"""
    try:
        response = requests.post(f"{BACKEND_URL}/api/v1/interaction-check", json=drug_names, timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"is_safe": True, "warnings": []}
    except Exception:
        return {"is_safe": True, "warnings": []}

# ==================== [웹 화면 UI 구성] ====================
st.set_page_config(page_title="스마트 의약품 종합 식별 시스템", layout="centered")

st.title("의약품 안전 식별 시스템")
st.write("알약 사진을 업로드하면 AI 분석 및 실시간 DUR(병용금기/임부·노인 금기) 검증을 수행합니다.")
st.markdown("---")

# 사진 업로드 기능
st.subheader("알약 사진 업로드")
uploaded_file = st.file_uploader("알약 사진을 업로드하세요", type=["jpg", "png", "jpeg"])

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
                if len(detected_pills) >= 2:
                    with st.spinner("검출된 알약 간의 병용금기(DUR) 상호작용 검증 중..."):
                        interaction_data = check_together_interaction(detected_pills)
                    
                    if not interaction_data.get("is_safe", True):
                        st.error("**[DUR 병용금기 위험] 함께 복용하면 안 되는 알약 조합이 발견되었습니다!**")
                        for warning in interaction_data.get("warnings", []):
                            st.write(f"- **{warning['drug_a']}** + **{warning['drug_b']}** ({warning['warning_type']}): {warning['description']}")
                    else:
                        st.success("**[DUR 안전]** 검출된 알약 간의 병용금기 위험이 없습니다.")
                
                # 가장 먼저 주가 되는 첫 번째 알약을 기준으로 상세 가이드 출력
                target_pill = detected_pills[0]
                
                with st.spinner("서버를 통해 식약처 공식 정보 요청 중..."):
                    pill_data = search_pill_from_server(target_pill)
                
                if pill_data is not None:
                    st.balloons() # 전체 성공 축하 효과
                    
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
                            if preg_result.get("has_warning"):
                                st.error("**임부금기 경고약물**")
                            else:
                                st.success("임부 복용 비교적 안전")
                        with dur_col2:
                            if elder_result.get("has_warning"):
                                st.warning("**노인주의 필요약물**")
                            else:
                                st.success("노인 복용 비교적 안전")
                    
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
