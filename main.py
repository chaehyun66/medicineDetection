"""
의약품 정보 서비스 API 서버
===========================
- 의약품 정보 조회 (공공데이터포털)
- 병용금기 확인 (DUR API)
- 의약품 검색
- 알약 객체 탐지 (Roboflow)
"""

from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import urllib.request
import urllib.parse
import json
import os
import tempfile
from roboflow import Roboflow

app = FastAPI(
    title="의약품 정보 서비스 API",
    description="의약품 정보 조회, 병용금기 확인 및 알약 객체 탐지",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= API 키 설정 =================
# .env 파일이나 환경 변수에서 키를 불러옵니다.
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "YOUR_API_KEY")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "YOUR_ROBOFLOW_KEY")

# ============= Roboflow 프로젝트 설정 =============
ROBOFLOW_WORKSPACE = "iwonhs-workspace-8vkwl"
ROBOFLOW_PROJECT_ID = "pill-detection-final-0fjal"
ROBOFLOW_VERSION = 1  # 학습 모델 버전에 맞게 수정하세요


# ============== 데이터 모델 ==============
class PillInfo(BaseModel):
    item_name: str          # 품목명
    entp_name: Optional[str] = None  # 업체명
    efficacy: Optional[str] = None   # 효능효과
    usage: Optional[str] = None      # 용법용량
    caution: Optional[str] = None    # 주의사항
    appearance: Optional[str] = None # 외형정보
    item_seq: Optional[str] = None   # 품목기준코드

class InteractionResult(BaseModel):
    drug_a: str
    drug_b: str
    warning_type: str       # 병용금기, 특정연령대금기, 임부금기 등
    description: str


# ============== API 엔드포인트 ==============

@app.get("/")
async def root():
    return {"message": "의약품 정보 서비스 API", "version": "1.1.0"}


@app.get("/api/v1/pill/search", response_model=List[PillInfo])
async def search_pill(
    name: str = Query(..., description="의약품명"),
    num_of_rows: int = Query(default=10, le=100)
):
    """의약품 검색 - 이름으로 검색"""
    try:
        url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        params = {
            "serviceKey": API_KEY,
            "itemName": name,
            "type": "json",
            "numOfRows": str(num_of_rows)
        }

        query_string = urllib.parse.urlencode(params, safe='=')
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        items = data.get("body", {}).get("items", [])
        if not items:
            return []

        results = []
        for item in items:
            results.append(PillInfo(
                item_name=item.get("itemName", ""),
                entp_name=item.get("entpName", ""),
                efficacy=item.get("efcyQesitm", ""),
                usage=item.get("useMethodQesitm", ""),
                caution=item.get("atpnQesitm", ""),
                item_seq=item.get("itemSeq", "")
            ))

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pill/detail/{item_seq}", response_model=PillInfo)
async def get_pill_detail(item_seq: str):
    """의약품 상세 정보 - 품목기준코드로 조회"""
    try:
        url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        params = {
            "serviceKey": API_KEY,
            "itemSeq": item_seq,
            "type": "json"
        }

        query_string = urllib.parse.urlencode(params, safe='=')
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        items = data.get("body", {}).get("items", [])
        if not items:
            raise HTTPException(status_code=404, detail="의약품 정보 없음")

        item = items[0]
        return PillInfo(
            item_name=item.get("itemName", ""),
            entp_name=item.get("entpName", ""),
            efficacy=item.get("efcyQesitm", ""),
            usage=item.get("useMethodQesitm", ""),
            caution=item.get("atpnQesitm", ""),
            item_seq=item.get("itemSeq", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pill/identify")
async def identify_pill(
    color: Optional[str] = Query(default=None, description="색상 (하양, 노랑, 주황 등)"),
    shape: Optional[str] = Query(default=None, description="모양 (원형, 타원형, 장방형 등)"),
    mark: Optional[str] = Query(default=None, description="식별문자"),
    num_of_rows: int = Query(default=10, le=100)
):
    """낱알 식별 정보 조회 - 색상, 모양, 식별문자로 검색"""
    try:
        url = "http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService01/getMdcinGrnIdntfcInfoList01"
        params = {
            "serviceKey": API_KEY,
            "type": "json",
            "numOfRows": str(num_of_rows)
        }

        if color:
            params["item_color"] = color
        if shape:
            params["drug_shape"] = shape
        if mark:
            params["mark_code_front"] = mark

        query_string = urllib.parse.urlencode(params, safe='=')
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        items = data.get("body", {}).get("items", [])

        results = []
        for item in items:
            results.append({
                "item_name": item.get("ITEM_NAME", ""),
                "entp_name": item.get("ENTP_NAME", ""),
                "item_seq": item.get("ITEM_SEQ", ""),
                "appearance": f"{item.get('DRUG_SHAPE', '')} {item.get('COLOR_CLASS1', '')}",
                "mark_front": item.get("MARK_CODE_FRONT", ""),
                "mark_back": item.get("MARK_CODE_BACK", ""),
                "image_url": item.get("ITEM_IMAGE", "")
            })

        return {"count": len(results), "items": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/interaction-check")
async def check_interaction(drug_names: List[str]):
    """병용금기 확인 - 여러 약물 간 상호작용 체크"""
    if len(drug_names) < 2:
        raise HTTPException(status_code=400, detail="2개 이상의 약물명 필요")

    warnings = []

    try:
        url = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03"

        for i, drug_a in enumerate(drug_names):
            params = {
                "serviceKey": API_KEY,
                "itemName": drug_a,
                "type": "json",
                "numOfRows": "100"
            }

            query_string = urllib.parse.urlencode(params, safe='=')
            full_url = f"{url}?{query_string}"

            req = urllib.request.Request(full_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            items = data.get("body", {}).get("items", [])

            for item in items:
                mixture_name = item.get("MIXTURE_ITEM_NAME", "")
                for drug_b in drug_names[i+1:]:
                    if drug_b.lower() in mixture_name.lower():
                        warnings.append(InteractionResult(
                            drug_a=drug_a,
                            drug_b=drug_b,
                            warning_type=item.get("TYPE_NAME", "병용금기"),
                            description=item.get("PROHBT_CONTENT", "병용 시 주의 필요")
                        ))

        return {
            "checked_drugs": drug_names,
            "warnings": warnings,
            "warning_count": len(warnings),
            "is_safe": len(warnings) == 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/dur/elderly/{item_seq}")
async def check_elderly_caution(item_seq: str):
    """특정연령대금기 확인 (노인 주의)"""
    try:
        url = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03/getSpcifyAgrdeTabooInfoList03"
        params = {
            "serviceKey": API_KEY,
            "itemSeq": item_seq,
            "type": "json"
        }

        query_string = urllib.parse.urlencode(params, safe='=')
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        items = data.get("body", {}).get("items", [])

        return {
            "item_seq": item_seq,
            "has_warning": len(items) > 0,
            "warnings": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/dur/pregnant/{item_seq}")
async def check_pregnant_caution(item_seq: str):
    """임부금기 확인"""
    try:
        url = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03/getPwnmTabooInfoList03"
        params = {
            "serviceKey": API_KEY,
            "itemSeq": item_seq,
            "type": "json"
        }

        query_string = urllib.parse.urlencode(params, safe='=')
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        items = data.get("body", {}).get("items", [])

        return {
            "item_seq": item_seq,
            "has_warning": len(items) > 0,
            "warnings": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/pill/detect")
async def detect_pill(file: UploadFile = File(...)):
    """이미지를 업로드하여 Roboflow 모델로 알약 객체 탐지"""
    if not ROBOFLOW_API_KEY or ROBOFLOW_API_KEY == "YOUR_ROBOFLOW_KEY":
        raise HTTPException(status_code=500, detail="서버에 Roboflow API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")

    temp_path = ""
    try:
        # 업로드된 이미지를 임시 파일로 저장 (Roboflow SDK 요구사항)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Roboflow 클라이언트 초기화 및 모델 로드
        rf = Roboflow(api_key=ROBOFLOW_API_KEY)
        project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT_ID)
        model = project.version(ROBOFLOW_VERSION).model
        
        # 모델 예측 실행 (신뢰도 40%, 겹침 허용 30% 기준)
        prediction = model.predict(temp_path, confidence=40, overlap=30).json()
        
        # 분석이 끝난 임시 파일 삭제
        os.remove(temp_path)
        
        return {
            "filename": file.filename, 
            "predictions": prediction
        }
        
    except Exception as e:
        # 에러 발생 시 임시 파일 찌꺼기 방지용 삭제 처리
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"이미지 객체 탐지 중 오류 발생: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)