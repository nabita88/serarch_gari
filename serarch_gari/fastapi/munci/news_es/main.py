from __future__ import annotations
import os
import pandas as pd
import yaml
import pymysql

from .cli import parse_args
from .embedding import embedding_dim
from .es_client import connect_es
from .index_schema import create_index, recreate_index
from .preprocess import docs_generator
from elasticsearch import helpers


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    sep = args.sep
    if sep is None:
        sep = "\t" if args.csv.lower().endswith(".tsv") else ","

    cols = {
        "date": args.col_date,
        "category": args.col_category,
        "title": args.col_title,
        "publisher": args.col_publisher,
        "url": args.col_url,
        "companies": args.col_companies
    }

    es = connect_es(args.es_host, args.es_user, args.es_pass)

    emb_dim = embedding_dim(args.embed_model) if args.use_embedding else 0
    if args.recreate_index:
        print(f"[정보] 인덱스 재생성: {args.index}")
        recreate_index(es, args.index)
    create_index(es, args.index, args.use_embedding, emb_dim)
    print(f"[정보] 인덱스 준비 완료: {args.index} (임베딩={'사용' if args.use_embedding else '비사용'})")

    if args.use_ai_events:
        print("[경고] AI 이벤트 추출 활성화 - 처리 속도가 매우 느립니다")
        print("[정보] 이벤트 추출에 rumerapi (HyperCLOVA + GPT-4) 사용")
    else:
        print("[정보] 규칙 기반 이벤트 추출 사용 (빠름)")

    conn = None
    if args.use_mariadb:
        try:
            with open('config.yml', 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            db = cfg.get('mariadb', {})
            if db:
                conn = pymysql.connect(
                    host=db.get('host', args.mysql_host or 'localhost'),
                    port=int(db.get('port', args.mysql_port)),
                    user=db.get('user', args.mysql_user),
                    password=db.get('password', args.mysql_pass),
                    database=db.get('database', args.mysql_db),
                    charset='utf8mb4',
                    autocommit=True
                )
        except Exception as e:
            print(f"[경고] MariaDB 설정 로드/연결 실패: {e}")
            conn = None

    usecols = [cols["date"], cols["category"], cols["title"], cols["publisher"], cols["url"], cols["companies"]]
    try:
        for chunk in pd.read_csv(args.csv, sep=sep, chunksize=args.chunk_size, usecols=usecols, dtype=str,
                                 encoding='utf-8'):
            helpers.bulk(
                es,
                docs_generator(
                    chunk,
                    cols,
                    args.use_embedding,
                    args.embed_model,
                    args.index,
                    args.use_ai_events
                ),
                chunk_size=1000
            )
    except UnicodeDecodeError:
        for enc in ['cp949', 'euc-kr', 'utf-8-sig']:
            try:
                for chunk in pd.read_csv(args.csv, sep=sep, chunksize=args.chunk_size, usecols=usecols, dtype=str,
                                         encoding=enc):
                    helpers.bulk(
                        es,
                        docs_generator(
                            chunk,
                            cols,
                            args.use_embedding,
                            args.embed_model,
                            args.index,
                            args.use_ai_events
                        ),
                        chunk_size=1000
                    )
                break
            except Exception as e:
                print(f"[경고] CSV({enc}) 로딩 실패: {e}")

    if args.smoke_query:
        from .search import smoke_search
        smoke_search(es, args.index, args.smoke_query, args.use_embedding, args.embed_model)


if __name__ == "__main__":
    main()
