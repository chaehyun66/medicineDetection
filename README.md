# AI 기반 알약 식별 및 의약품 정보 제공 서비스 

알약 사진을 업로드하거나 카메라로 촬영하면 YOLO 모델이 알약을 식별하고, 
공공데이터 포털 API를 통해 효능/효과, 복용 방법, 주의사항과 DUR 정보를 제공하는 웹 서비스입니다. 

> 본 서비스의 의약품 정보는 참고용이며, 실제 복용 전 의사 또는 약사와 상담해야합니다.





## 주요 기능 

- 알약 사진 업로드
- 모바일, PC 카메라 촬영
- YOLO 모델을 이용한 알약 식별
- 인식 결과 표시
- 효능, 효과 / 용법, 용량 / 주의사항 조회
- 임부금기 및 연령별 주의정보 조회
- 여러 알약 검출 시 병용 금기 확인
- e약은요에서 조회되지 않는 의약품의 공식 정보 보완





## 개발 과정 





### 1. 데이터셋 제작 

13종류의 알약을 다양한 방향과 환경에서 촬영했습니다. 촬영한 이미지는 Roboflow에 업로드하여 
클래스 분류, 라벨링, 데이터셋 전처리를 진행했습니다. 

학습 클래스 : 
1. Celetec
2. Erdo Cough
3. Ilsung Claruthromycin
4. LadyOne
5. Mephsol
6. Otilen
7. acepen
8. artec
9. cefaroxil
10. penlex
11. rebakim
12. trimela
13. viopen





### 2. 모델 학습 

Roboflow에서 제작한 데이터셋을 Google Colab으로 가져와 Ultralytics YOLO 모델을 학습했습니다. 
학습 결과 생성된 'best.pt' 파일을 웹사이트의 알약 식별 모델로 사용했습니다. 





### 3. 의약품 매핑 

모델의 영문 클래스명은 공공데이터의 공식 한글 품목명과 다르므로 'pill_mapping.json'을 이용해 연결했습니다.

```

{
 "Celetec" : {
 "item_name" : "쎄레텍정",
 "item_seq" : "202302403"
 }
}

```




### 4. 공공데이터 연동 

FastAPI 서버에서 다음 공공데이터를 조회합니다. 

- 의약품개요정보 e약은요
- 의약품 낱알식별 정보
- DUR 품목정보
- 병용금기 정보
- 임부금기 및 특정 연령대 주의보

e약은요에서 제공되지 않는 의약품은 의약품안전나라의 공식 정보를 바탕으로 pill_manual_info.json에 보완했습니다. 





### 5. 웹사이트 제작 

Streamlit으로 사진 업로드, 카메라 촬영, 분석 결과와 의약품 정보를 보여주는 반응형 웹사이트를 제작했습니다. 





## 시스템 구성 

```
[ 사용자 ]           ->     [ Streamlit 웹사이트 ]    ->    [ YOLO best.pt 모델 ] 
사진 업로드 또는 촬영                                           알약 클래스 예측 

-> [ pill_mapping.json ]       ->      [ FastAPI 서버 ]      ->     [ 공공데이터포털 API ] 
공식 품목명, 품목기준코드 변환

-> [ 효능, 복용법, 주의사항, DUR 정보 표시 ] 

```




## 기술 스택

- Python
- Streamlit
- FastAPI
- Ultralytics YOLO
- PyTorch
- Roboflow
- Google Colab
- 공공데이터포털 Open API
- Render
- Streamlit Community Cloud






## 프로젝트 구조 
```
pill_project/
├── app_ui_base.py          # Streamlit 웹사이트
├── main.py                 # FastAPI 백엔드 서버
├── best.pt                 # YOLO 학습 모델
├── pill_mapping.json       # 모델 클래스와 의약품 매핑
├── pill_manual_info.json   # 수동 보완 의약품 정보
├── requirements.txt        # Streamlit 의존성
├── requirements-render.txt # Render 백엔드 의존성
├── packages.txt            # Linux 시스템 패키지
├── .streamlit/
│   └── config.toml
├── .env                    # 로컬 환경변수, Git 제외
└── README.md
```






## 로컬 실행 방법 





### 1. 가상환경 생성 



```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```



### 2. 환경변수 설정 

.env 파일을 생성합니다. 

```
DATA_GO_KR_API_KEY = 공공데이터_API키
BACKEND_URL = http://127.0.0.1:8000
MODEL_PATH = best.pt
PILL_MAPPING_PATH = pill_mapping.json
MANUAL_INFO_PATH = pill_manual_info.json
```



### 3. FastAPI 실행 

```
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```



### 4. Streamlit 실행 

새 Powershell 창에서 실행합니다. 

```
streamlit run app_ui_base.py --server.port 8501
```



## 배포 

- 웹사이트 : Streamlit Community Cloud
- FastAPI 서버 : Render
- 소스 코드 : GitHub

웹사이트 : https://pill-detection.streamlit.app/   
백엔드 : https://pilldetection.onrender.com



## 주의 및 한계 

- 현재 학습된 13종류의 알약만 식별할 수 있습니다.
- 촬영 각도, 조명, 이미지 품질에 따라 정확도가 달라질 수 있습니다.
- 외형이 비슷한 의약품은 오인식될 수 있습니다.
- 공공데이터에 없는 정보는 의약품안전나라의 공식 자료로 보완했습니다.



### 팀원 

팀장 : 황채현(2516842)   
팀원1 : 정유진(2512907)  
팀원2 : 조효원(2512455)   



### 정보 출처 
- 공공데이터포털 (https://www.data.go.kr/)
- 의약품안전나라 (https://nedrug.mfds.go.kr/index)
- Roboflow (https://roboflow.com/)
- Ultralytics (https://www.ultralytics.com/)
