"""
CSV 파일을 MariaDB로 업로드하는 스크립트
config.yml의 데이터베이스 설정을 사용합니다.
"""
import logging
from pathlib import Path
from urllib.parse import quote_plus
import re

import pandas as pd
import yaml
from sqlalchemy import create_engine, text, Table, Column, MetaData, String

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "./config.yml") -> dict:
    """config.yml 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        if 'database' not in cfg:
            raise KeyError("config.yml에 'database' 섹션이 없습니다.")
        required = {'host', 'port', 'database', 'username', 'password'}
        missing = required - set(cfg['database'])
        if missing:
            raise KeyError(f"database 설정 누락: {', '.join(sorted(missing))}")
        return cfg
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML: {e}")
        raise


def create_db_engine(db_config: dict):
    """SQLAlchemy 엔진 생성 (비밀번호 등 URL 인코딩 포함)"""
    user = quote_plus(str(db_config['username']))
    pwd = quote_plus(str(db_config['password']))
    host = db_config['host']
    port = int(db_config.get('port', 3306))
    db   = db_config['database']

    conn_str = (
        f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
        f"?charset=utf8mb4"
    )

    # pool_pre_ping: 장시간 유휴 후 끊어진 커넥션 자동 감지
    # pool_recycle: 오래된 커넥션 재활용 시간
    engine = create_engine(
        conn_str,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
    )
    return engine


def _validate_table_name(table_name: str) -> str:
    """간단한 식별자 검증 + MySQL 백틱 이스케이프"""
    if not re.match(r"^[A-Za-z0-9_]+$", table_name):
        raise ValueError("table_name은 영문/숫자/언더스코어만 허용합니다.")
    return f"`{table_name}`"


def upload_csv_to_mariadb(
    csv_file: str,
    table_name: str,
    config_path: str = "../config.yml",
    if_exists: str = 'replace',
    chunksize: int = 1000,
    enforce_table_charset: bool = True,  # 기본값을 True로 변경
):
    """
    CSV 파일을 MariaDB 테이블로 업로드
    """
    try:
        # 설정 로드
        logger.info("Loading configuration...")
        config = load_config(config_path)
        db_config = config['database']

        # CSV 파일 읽기 (인코딩 폴백)
        logger.info(f"Reading CSV file: {csv_file}")
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding='cp949')
        
        # 컬럼명 공백 제거
        df.columns = df.columns.str.strip()
        
        logger.info(f"CSV loaded. rows={len(df)} cols={len(df.columns)}")
        logger.info(f"Columns: {list(df.columns)}")

        # 미리보기
        logger.info("\n" + df.head(3).to_string(index=False))

        # 엔진 생성
        logger.info("Creating database engine...")
        engine = create_db_engine(db_config)

        # 업로드
        logger.info(f"Uploading -> {table_name} (chunksize={chunksize})")
        
        # 테이블 생성 시 utf8mb4 charset 강제
        if if_exists == 'replace':
            with engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                conn.commit()
        
        # VARCHAR 길이 지정 (한글 포함이므로 충분히 큰 값)
        dtype_dict = {}
        for col in df.columns:
            max_len = df[col].astype(str).str.len().max()
            length = min(max(max_len + 100, 255), 5000)  # 최소 255, 최대 5000
            dtype_dict[col] = String(length=length, collation='utf8mb4_unicode_ci')
        
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists='append',
            index=False,
            chunksize=chunksize,
            method='multi',
            dtype=dtype_dict
        )
        logger.info("Upload done.")

        # 업로드 검증
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) AS cnt FROM `{table_name}`"))
            row_count = result.scalar_one()
        logger.info(f"Row count check: {row_count}")

        return True

    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file}")
        raise
    except pd.errors.EmptyDataError:
        logger.error(f"CSV file is empty: {csv_file}")
        raise
    except Exception as e:
        logger.error(f"Error uploading CSV to MariaDB: {e}")
        raise
    finally:
        if 'engine' in locals():
            engine.dispose()


def main():
    """메인 실행 함수"""
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    csv_file = current_dir / 'comprehensive_analyzed_news_2025_10_13last_v1.csv'
    config_path = project_root / 'config.yml'

    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        logger.info("Available CSV files in current directory:")
        for file in current_dir.glob("*.csv"):
            logger.info(f"  - {file.name}")
        return
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return

    table_name = 'comprehensive_analyzed_news'

    logger.info("=" * 60)
    logger.info("CSV to MariaDB Upload")
    logger.info("=" * 60)

    upload_csv_to_mariadb(
        csv_file=str(csv_file),
        table_name=table_name,
        config_path=str(config_path),
        if_exists='replace',
        chunksize=10,
        enforce_table_charset=True,
    )

    logger.info("=" * 60)
    logger.info("Upload completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
