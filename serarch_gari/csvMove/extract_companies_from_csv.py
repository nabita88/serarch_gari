"""
CSV 파일에서 회사명과 종목코드 추출

CSV 형식:
날짜,카테고리,제목,언론사,링크

출력:
날짜,카테고리,제목,언론사,링크,회사명,종목코드
"""
import sys
import csv
import os
from pathlib import Path
from typing import List, Dict, Optional
import time

# 프로젝트 루트 경로 추가
# csvMove 폴더에서 실행되므로 상위 폴더(PythonProject10)가 루트
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# munci 폴더의 company_extractor 사용
try:
    from munci.lastsa.company_extractor.extractor import FinalCompanyExtractor
except ImportError as e:
    print(f"❌ Import 오류: {e}")
    print(f"현재 경로: {Path(__file__).resolve()}")
    print(f"프로젝트 루트: {project_root}")
    print(f"sys.path: {sys.path[:3]}")
    raise


class CompanyExtractorFromCSV:
    """CSV에서 회사명과 종목코드 추출"""
    
    def __init__(self, db_config: Optional[Dict] = None):
        """
        Args:
            db_config: DB 설정 (선택사항)
        """
        print("=" * 70)
        print("회사명 및 종목코드 추출기 초기화 중...")
        print("=" * 70)
        
        # FinalCompanyExtractor 초기화
        # data_path를 munci/lastsa/sysm으로 지정
        sysm_path = project_root / 'munci' / 'lastsa' / 'sysm'
        
        self.extractor = FinalCompanyExtractor(
            data_path=str(sysm_path),
            db_config=db_config
        )
        
        print("\n✅ 초기화 완료!\n")
    
    def extract_companies_from_title(self, title: str, verbose: bool = False) -> Dict[str, List[str]]:
        """
        제목에서 회사명과 종목코드 추출
        
        Args:
            title: 뉴스 제목
            verbose: 상세 로그 출력
            
        Returns:
            {
                'companies': ['삼성전자', 'SK하이닉스'],
                'tickers': ['005930', '000660']
            }
        """
        try:
            # 회사명 추출
            result = self.extractor.extract_companies(title, verbose=verbose)
            
            companies = result.companies
            tickers = []
            
            # 종목코드 추출
            for company in companies:
                if company in result.company_details:
                    detail = result.company_details[company]
                    if detail.stock_code:
                        tickers.append(detail.stock_code)
            
            return {
                'companies': companies,
                'tickers': tickers
            }
            
        except Exception as e:
            print(f"  ⚠️ 추출 실패: {e}")
            return {
                'companies': [],
                'tickers': []
            }
    
    def process_csv(
        self,
        input_csv: str,
        output_csv: str,
        encoding: str = 'utf-8',
        verbose: bool = True
    ):
        """
        CSV 파일 처리
        
        Args:
            input_csv: 입력 CSV 파일 경로
            output_csv: 출력 CSV 파일 경로
            encoding: 파일 인코딩
            verbose: 진행 상황 출력
        """
        print("=" * 70)
        print(f"CSV 처리 시작")
        print(f"  입력: {input_csv}")
        print(f"  출력: {output_csv}")
        print("=" * 70)
        
        # 입력 파일 확인
        if not os.path.exists(input_csv):
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_csv}")
        
        # 출력 디렉토리 생성
        output_dir = os.path.dirname(output_csv)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"  📁 출력 디렉토리 생성: {output_dir}")
        
        # 통계
        total_rows = 0
        success_rows = 0
        error_rows = 0
        start_time = time.time()
        
        # 인코딩 시도 목록
        encodings_to_try = [encoding, 'utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        
        input_file = None
        reader = None
        
        # 인코딩 자동 감지
        for enc in encodings_to_try:
            try:
                input_file = open(input_csv, 'r', encoding=enc, newline='')
                reader = csv.DictReader(input_file)
                # 첫 줄 읽기 테스트
                first_row = next(reader)
                input_file.seek(0)
                # 헤더 다시 읽기
                reader = csv.DictReader(input_file)
                print(f"  ✅ 인코딩 감지: {enc}")
                break
            except (UnicodeDecodeError, StopIteration):
                if input_file:
                    input_file.close()
                continue
            except Exception as e:
                if input_file:
                    input_file.close()
                continue
        
        if not reader:
            raise ValueError(f"파일을 읽을 수 없습니다. 인코딩을 확인해주세요: {input_csv}")
        
        try:
            # 헤더 확인
            fieldnames = reader.fieldnames
            print(f"  📋 입력 컬럼: {fieldnames}")
            
            # 필수 컬럼 확인
            if '제목' not in fieldnames:
                raise ValueError("'제목' 컬럼이 없습니다!")
            
            # 출력 헤더 (기존 + 회사명 + 종목코드)
            output_fieldnames = list(fieldnames) + ['회사명', '종목코드']
            
            # 출력 파일 열기
            with open(output_csv, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
                writer.writeheader()
                
                # 각 행 처리
                for idx, row in enumerate(reader, start=1):
                    total_rows += 1
                    
                    try:
                        title = row.get('제목', '')
                        
                        if not title or title.strip() == '':
                            if verbose:
                                print(f"  [{idx}] ⚠️ 제목 없음")
                            row['회사명'] = ''
                            row['종목코드'] = ''
                            writer.writerow(row)
                            error_rows += 1
                            continue
                        
                        # 회사명 추출
                        result = self.extract_companies_from_title(title, verbose=False)
                        
                        companies = result['companies']
                        tickers = result['tickers']
                        
                        # 쉼표로 구분하여 저장
                        row['회사명'] = ','.join(companies) if companies else ''
                        row['종목코드'] = ','.join(tickers) if tickers else ''
                        
                        writer.writerow(row)
                        success_rows += 1
                        
                        if verbose and (idx % 10 == 0 or companies):
                            company_info = f"{companies}" if companies else "없음"
                            ticker_info = f"{tickers}" if tickers else "없음"
                            print(f"  [{idx}/{total_rows}] {title[:40]}... → 회사: {company_info}, 코드: {ticker_info}")
                        
                    except Exception as e:
                        print(f"  ❌ [{idx}] 처리 실패: {e}")
                        row['회사명'] = ''
                        row['종목코드'] = ''
                        writer.writerow(row)
                        error_rows += 1
                        continue
            
        finally:
            if input_file:
                input_file.close()
        
        # 결과 출력
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("✅ 처리 완료!")
        print("=" * 70)
        print(f"  총 행 수: {total_rows}개")
        print(f"  성공: {success_rows}개")
        print(f"  실패/빈값: {error_rows}개")
        print(f"  소요 시간: {elapsed:.1f}초 ({total_rows/elapsed:.1f}행/초)")
        print(f"  출력 파일: {output_csv}")
        print("=" * 70)
    
    def process_folder(
        self,
        input_folder: str,
        output_folder: str,
        encoding: str = 'utf-8',
        verbose: bool = True
    ):
        """
        폴더 내 모든 CSV 파일 처리
        
        Args:
            input_folder: 입력 폴더 경로
            output_folder: 출력 폴더 경로
            encoding: 파일 인코딩
            verbose: 진행 상황 출력
        """
        print("\n" + "=" * 70)
        print("📁 폴더 처리 시작")
        print(f"  입력 폴더: {input_folder}")
        print(f"  출력 폴더: {output_folder}")
        print("=" * 70)
        
        # 입력 폴더 확인
        if not os.path.exists(input_folder):
            raise FileNotFoundError(f"입력 폴더를 찾을 수 없습니다: {input_folder}")
        
        # 출력 폴더 생성
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"  📁 출력 폴더 생성: {output_folder}")
        
        # CSV 파일 찾기
        csv_files = []
        for file in os.listdir(input_folder):
            if file.lower().endswith('.csv'):
                csv_files.append(file)
        
        if not csv_files:
            print(f"  ⚠️ CSV 파일을 찾을 수 없습니다: {input_folder}")
            return
        
        print(f"  📄 발견된 CSV 파일: {len(csv_files)}개")
        print()
        
        # 각 파일 처리
        for idx, filename in enumerate(csv_files, start=1):
            print(f"\n{'='*70}")
            print(f"[{idx}/{len(csv_files)}] 처리 중: {filename}")
            print('='*70)
            
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            
            try:
                self.process_csv(input_path, output_path, encoding=encoding, verbose=verbose)
            except Exception as e:
                print(f"  ❌ 파일 처리 실패: {e}")
                continue
        
        print("\n" + "=" * 70)
        print("🎉 모든 파일 처리 완료!")
        print("=" * 70)


def main():
    """CLI 실행"""
    import argparse
    from dotenv import load_dotenv
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="CSV 파일에서 회사명과 종목코드 추출"
    )
    
    parser.add_argument(
        '--input-folder',
        default=r'C:\Users\ll\Downloads\new\drive20251020\PythonProject10\csvjunchri',
        help='입력 CSV 폴더 경로'
    )
    
    parser.add_argument(
        '--output-folder',
        default=r'C:\Users\ll\Downloads\new\drive20251020\PythonProject10\csvjunchrifinish',
        help='출력 CSV 폴더 경로'
    )
    
    parser.add_argument(
        '--input-file',
        help='단일 CSV 파일 처리 (폴더 대신)'
    )
    
    parser.add_argument(
        '--output-file',
        help='출력 CSV 파일 경로 (단일 파일 처리시)'
    )
    
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='파일 인코딩 (기본: utf-8)'
    )
    
    parser.add_argument(
        '--use-db',
        action='store_true',
        help='DB 연결 사용 (종목코드 조회)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )
    
    args = parser.parse_args()
    
    # DB 설정 (선택사항)
    db_config = None
    if args.use_db:
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'username': os.getenv('DB_USERNAME'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_DATABASE')
        }
    
    # 추출기 초기화
    extractor = CompanyExtractorFromCSV(db_config=db_config)
    
    # 단일 파일 처리
    if args.input_file and args.output_file:
        extractor.process_csv(
            args.input_file,
            args.output_file,
            encoding=args.encoding,
            verbose=args.verbose
        )
    
    # 폴더 처리
    else:
        extractor.process_folder(
            args.input_folder,
            args.output_folder,
            encoding=args.encoding,
            verbose=args.verbose
        )


if __name__ == '__main__':
    main()
