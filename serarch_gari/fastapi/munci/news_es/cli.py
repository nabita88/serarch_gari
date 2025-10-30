from __future__ import annotations
import os, argparse

from .config import CSV_FILE, INDEX_NAME


def parse_args():
    ap = argparse.ArgumentParser(description="CSV → preprocess → ES index → MariaDB meta")
    ap.add_argument("--csv", default=CSV_FILE, help="입력 CSV/TSV 경로")
    ap.add_argument("--sep", default=None, help="구분자(기본: 확장자에 따라 자동)")

    ap.add_argument("--es-host", default=os.getenv("ES_HOST", "http://localhost:9200"))
    ap.add_argument("--es-user", default=os.getenv("ES_USER"))
    ap.add_argument("--es-pass", default=os.getenv("ES_PASS"))
    ap.add_argument("--index", default=INDEX_NAME, help="Elasticsearch 인덱스명")
    ap.add_argument("--recreate-index", action="store_true", help="인덱스를 삭제 후 재생성")
    ap.add_argument("--use-embedding", action="store_true", help="제목 임베딩 생성 + dense_vector 필드 포함")
    ap.add_argument("--embed-model", default="intfloat/multilingual-e5-large", help="임베딩 모델명(sentence-transformers)")

    ap.add_argument("--use-ai-events", action="store_true",
                    help="rumerapi를 사용한 AI 이벤트 추출 (HyperCLOVA + GPT-4, 느리지만 정확)")

    ap.add_argument("--mysql-host", default=None, help="MariaDB 호스트")
    ap.add_argument("--mysql-port", type=int, default=3306, help="MariaDB 포트")
    ap.add_argument("--mysql-db", default=None, help="MariaDB 데이터베이스명")
    ap.add_argument("--mysql-user", default=None, help="MariaDB 사용자명")
    ap.add_argument("--mysql-pass", default=None, help="MariaDB 비밀번호")
    ap.add_argument("--create-tables", action="store_true", help="테이블 생성")
    ap.add_argument("--chunk-size", type=int, default=20000, help="CSV 청크 사이즈")
    ap.add_argument("--use-mariadb", action="store_true", default=True, help="MariaDB 저장 활성화")

    ap.add_argument("--save-parquet", action="store_true", help="전처리 결과 Parquet 저장")
    ap.add_argument("--save-jsonl", action="store_true", help="전처리 결과 JSONL 저장(ES bulk에 활용)")
    ap.add_argument("--out-dir", default="./out", help="전처리 산출물 저장 폴더")
    ap.add_argument("--smoke-query", default=None, help="스모크 검색 질의(옵션)")

    ap.add_argument("--col-date", default="date")
    ap.add_argument("--col-category", default="category")
    ap.add_argument("--col-title", default="title")
    ap.add_argument("--col-publisher", default="publisher")
    ap.add_argument("--col-url", default="url")
    ap.add_argument("--col-companies", default="stock_name")

    return ap.parse_args()
