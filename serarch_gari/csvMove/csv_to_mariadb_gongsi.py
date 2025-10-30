"""
CSV 파일을 MariaDB로 업로드 (utf8mb4 안전 버전)
- 핵심: 테이블을 utf8mb4로 '생성'한 다음 데이터를 넣는다.
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import VARCHAR, TEXT, LONGTEXT
import yaml
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config():
    config_path = Path(__file__).parent.parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["database"]


def get_db_connection():
    db = load_config()
    engine = create_engine(
        f"mysql+pymysql://{db['username']}:{db['password']}@"
        f"{db['host']}:{db['port']}/{db['database']}",
        connect_args={"charset": "utf8mb4"},  # 커넥션도 utf8mb4
        pool_pre_ping=True,
    )
    return engine


def upload_csv_to_mariadb():
    logger.info("=" * 60)
    logger.info("CSV to MariaDB Upload (utf8mb4 safe)")
    logger.info("=" * 60)

    csv_path = Path(__file__).parent / "rumors_openDartReader.csv"
    if not csv_path.exists():
        logger.error(f"CSV not found: {csv_path}")
        return

    logger.info(f"Reading CSV: {csv_path}")
    # BOM 이 섞여 있을 때 컬럼명 깨짐 방지
    df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    engine = get_db_connection()

    # 문자형 컬럼을 utf8mb4로 '생성'되도록 dtype과 collation을 명시
    dtype = {
        "corp_code":    VARCHAR(20,  collation="utf8mb4_unicode_ci"),
        "corp_name":    VARCHAR(255, collation="utf8mb4_unicode_ci"),
        "stock_code":   VARCHAR(20,  collation="utf8mb4_unicode_ci"),
        "corp_cls":     VARCHAR(10,  collation="utf8mb4_unicode_ci"),
        "report_nm":    TEXT(collation="utf8mb4_unicode_ci"),
        "rcept_no":     VARCHAR(20,  collation="utf8mb4_unicode_ci"),
        "flr_nm":       VARCHAR(255, collation="utf8mb4_unicode_ci"),
        "rcept_dt":     VARCHAR(10,  collation="utf8mb4_unicode_ci"),  # 문자열로 저장
        "rm":           LONGTEXT(collation="utf8mb4_unicode_ci"),
        "viewer_url":   TEXT(collation="utf8mb4_unicode_ci"),
        "글제목":         TEXT(collation="utf8mb4_unicode_ci"),
        "글내용":         LONGTEXT(collation="utf8mb4_unicode_ci"),
        "verdict":      VARCHAR(50,  collation="utf8mb4_unicode_ci"),
        "summary":      LONGTEXT(collation="utf8mb4_unicode_ci"),
        "counterparty": VARCHAR(255, collation="utf8mb4_unicode_ci"),
    }

    table_name = "rumors_opendart"

    # if_exists='replace' : DROP → CREATE(utf8mb4) → INSERT 을 한 번에 수행
    logger.info(f"Creating table & uploading to: {table_name}")
    with engine.begin() as conn:
        df.to_sql(
            name=table_name,
            con=conn,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
            dtype=dtype,
        )
        total = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        logger.info(f"✓ Upload complete! Total rows: {total}")

    logger.info("=" * 60)
    engine.dispose()


if __name__ == "__main__":
    upload_csv_to_mariadb()
