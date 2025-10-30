import pandas as pd
from sqlalchemy import create_engine, text
import yaml
from pathlib import Path


def load_config():
    config_path = Path(__file__).parent.parent / 'config.yml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config['database']


def get_db_connection():
    db_config = load_config()
    engine = create_engine(
        f"mysql+pymysql://{db_config['username']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}",
        connect_args={"charset": "utf8mb4"}
    )
    return engine


def upload_csv_to_mariadb():
    print("Upload Stock Data to MariaDB")

    csv_path = Path(__file__).parent / 'stock_20251001_20251013.csv'

    print(f"Reading CSV file: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows")

    engine = get_db_connection()

    with engine.connect() as conn:
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS stock_daily_prices
                          (
                              날짜
                              DATE,
                              종목코드
                              VARCHAR
                          (
                              10
                          ),
                              종목명 VARCHAR
                          (
                              100
                          ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                              종가 DECIMAL
                          (
                              15,
                              2
                          ),
                              PRIMARY KEY
                          (
                              날짜,
                              종목코드
                          )
                              ) DEFAULT CHARSET=utf8mb4 COLLATE =utf8mb4_unicode_ci
                          """))
        conn.commit()

    print("Uploading to table: stock_daily_prices")
    df.to_sql(name='stock_daily_prices', con=engine, if_exists='append',
              index=False, chunksize=1000, method='multi')

    print("Upload complete!")
    engine.dispose()


if __name__ == "__main__":
    upload_csv_to_mariadb()