# 의약품 정보 API 서버

## API 엔드포인트

| 엔드포인트 | 메소드 | 기능 |
|-----------|--------|------|
| `/api/v1/pill/search?name=타이레놀` | GET | 의약품 검색 |
| `/api/v1/pill/detail/{item_seq}` | GET | 상세 정보 조회 |
| `/api/v1/pill/identify?color=하양&shape=원형` | GET | 낱알 식별 |
| `/api/v1/interaction-check` | POST | 병용금기 확인 |
| `/api/v1/dur/elderly/{item_seq}` | GET | 노인 주의 확인 |
| `/api/v1/dur/pregnant/{item_seq}` | GET | 임부 금기 확인 |

## 실행

```bash
pip install -r requirements.txt
export DATA_GO_KR_API_KEY=your_key
uvicorn main:app --reload --port 8000
```

## API 키 발급
https://www.data.go.kr 에서 신청:
- e약은요 API (의약품 정보)
- 의약품 낱알식별 정보 API
- DUR 품목정보 API (병용금기)
