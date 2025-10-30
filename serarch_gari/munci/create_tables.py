#!/usr/bin/env python
"""
필요한 테이블 생성 스크립트
"""
import os
import pymysql
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USERNAME'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_DATABASE'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def create_event_returns_history_table():
    """event_returns_history 테이블 생성"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS event_returns_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        
        -- 기본 정보
        stock_code VARCHAR(10) NOT NULL COMMENT '종목코드',
        event_date VARCHAR(8) NOT NULL COMMENT '이벤트 발생일 (YYYYMMDD)',
        event_code VARCHAR(100) NOT NULL COMMENT '이벤트 분류 코드',
        
        -- 앵커 정보
        anchor_date VARCHAR(8) NOT NULL COMMENT '앵커 거래일 (YYYYMMDD)',
        anchor_price DECIMAL(15, 2) NOT NULL COMMENT '기준가격',
        
        -- 수익률 정보
        return_1d DECIMAL(10, 6) COMMENT '1일 로그수익률',
        return_3d DECIMAL(10, 6) COMMENT '3일 로그수익률',
        return_5d DECIMAL(10, 6) COMMENT '5일 로그수익률',
        
        -- 추가 정보
        volume BIGINT DEFAULT 0 COMMENT '거래량',
        market_cap DECIMAL(20, 2) DEFAULT 0 COMMENT '시가총액',
        
        -- 메타 정보
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        -- 인덱스
        INDEX idx_stock_event (stock_code, event_code),
        INDEX idx_event_date (event_date),
        INDEX idx_event_code (event_code),
        UNIQUE KEY unique_event (stock_code, event_date, event_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='이벤트별 수익률 이력 테이블'
    """
    
    conn = None
    try:
        conn = pymysql.connect(**db_config)
        
        with conn.cursor() as cursor:
            # 테이블 생성
            cursor.execute(create_table_sql)
            conn.commit()
            print(" event_returns_history 테이블 생성 완료")
            
            # 테이블 확인
            cursor.execute("SHOW TABLES LIKE 'event_returns_history'")
            if cursor.fetchone():
                print(" 테이블 존재 확인")
                
                # 구조 확인
                cursor.execute("DESCRIBE event_returns_history")
                columns = cursor.fetchall()
                print("\n 테이블 구조:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]}")
            else:
                print(" 테이블 생성 실패")
                
    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def create_news_returns_table():
    """news_returns 테이블 생성 (뉴스 기반 수익률 이력)"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS news_returns (
        id INT AUTO_INCREMENT PRIMARY KEY,
        
        -- 뉴스 정보
        news_id VARCHAR(500) NOT NULL COMMENT '뉴스 URL',
        stock_code VARCHAR(10) NOT NULL COMMENT '종목코드',
        stock_name VARCHAR(100) NOT NULL COMMENT '종목명',
        event_code VARCHAR(100) NOT NULL COMMENT '이벤트 분류 코드',
        news_date DATE NOT NULL COMMENT '뉴스 날짜',
        
        -- 앵커 가격
        anchor_price DECIMAL(15, 2) NOT NULL COMMENT '기준가격',
        
        -- 수익률 정보
        return_1d DECIMAL(10, 6) COMMENT '1일 로그수익률',
        return_3d DECIMAL(10, 6) COMMENT '3일 로그수익률',
        return_5d DECIMAL(10, 6) COMMENT '5일 로그수익률',
        
        -- 메타 정보
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        -- 인덱스
        INDEX idx_stock_code (stock_code),
        INDEX idx_event_code (event_code),
        INDEX idx_news_date (news_date),
        INDEX idx_stock_event (stock_code, event_code),
        UNIQUE KEY unique_news_return (news_id(255), stock_code, event_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='뉴스 기반 수익률 이력 테이블'
    """
    
    conn = None
    try:
        conn = pymysql.connect(**db_config)
        
        with conn.cursor() as cursor:
            # 테이블 생성
            cursor.execute(create_table_sql)
            conn.commit()
            print(" news_returns 테이블 생성 완료")
            
            # 테이블 확인
            cursor.execute("SHOW TABLES LIKE 'news_returns'")
            if cursor.fetchone():
                print(" 테이블 존재 확인")
                
                # 구조 확인
                cursor.execute("DESCRIBE news_returns")
                columns = cursor.fetchall()
                print("\n 테이블 구조:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]}")
            else:
                print(" 테이블 생성 실패")
                
    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def check_existing_data():
    """기존 데이터 확인"""
    conn = None
    try:
        conn = pymysql.connect(**db_config)
        
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # rumors_opendart 테이블 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM rumors_opendart WHERE rcept_dt BETWEEN '20240101' AND '20241231'")
            result = cursor.fetchone()
            print(f"\n rumors_opendart 테이블:")
            print(f"  - 2024년 공시: {result['cnt']}건")
            
            # stock_list 테이블 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM stock_list WHERE stock_code IS NOT NULL")
            result = cursor.fetchone()
            print(f"\n stock_list 테이블:")
            print(f"  - 종목: {result['cnt']}개")
            
            # stock_daily_prices 테이블 확인
            cursor.execute("""
                SELECT COUNT(DISTINCT stock_code) as stocks, 
                       MIN(trade_date) as min_date, 
                       MAX(trade_date) as max_date
                FROM stock_daily_prices
            """)
            result = cursor.fetchone()
            print(f"\n💹 stock_daily_prices 테이블:")
            print(f"  - 종목수: {result['stocks']}개")
            print(f"  - 기간: {result['min_date']} ~ {result['max_date']}")
            
    except Exception as e:
        print(f"❌ 데이터 확인 실패: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("테이블 생성 스크립트")
    print("=" * 60)
    
    # news_returns 테이블만 생성
    create_news_returns_table()
    
    print("\n" + "=" * 60)
    print("✅ news_returns 테이블 생성 완료!")
    print("=" * 60)
