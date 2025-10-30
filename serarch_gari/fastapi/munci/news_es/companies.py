import sys
import csv
from pathlib import Path

from munci.lastsa.company_extractor.extractor import FinalCompanyExtractor


def extract_stock_codes(csv_path):
    extractor = FinalCompanyExtractor()

    results = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stock_name = row['종목명']
            stock_code_from_csv = row['종목코드']

            extraction_result = extractor.extract_companies(stock_name, verbose=False)

            extracted_ticker = ""
            canonical_name = ""

            if extraction_result.companies:
                first_company = extraction_result.companies[0]
                canonical_name = first_company

                if first_company in extraction_result.company_details:
                    company_info = extraction_result.company_details[first_company]
                    extracted_ticker = company_info.stock_code or ""

            results.append({
                '종목명': stock_name,
                'CSV종목코드': stock_code_from_csv,
                '추출된종목코드': extracted_ticker,
                '정식회사명': canonical_name,
                '일치여부': extracted_ticker == stock_code_from_csv if extracted_ticker else False
            })

    return results


def normalize_company(company_name: str) -> str:
    return company_name.strip()


def resolve_company(company_name: str):
    normalized = normalize_company(company_name)
    return [normalized], []


def load_alias_index():
    return {}


def main():
    csv_path = Path(__file__).parent / 'stock_20250901_20251003.csv'
    results = extract_stock_codes(csv_path)

    print(f"\n총 {len(results)}개 종목 처리")
    print(f"일치: {sum(1 for r in results if r['일치여부'])}개")
    print(f"불일치: {sum(1 for r in results if not r['일치여부'])}개")

    print("\n=== 불일치 항목 (처음 20개) ===")
    count = 0
    for r in results:
        if not r['일치여부']:
            print(f"종목명: {r['종목명']}, CSV: {r['CSV종목코드']}, 추출: {r['추출된종목코드']}, 정식명: {r['정식회사명']}")
            count += 1
            if count >= 20:
                break

    output_path = Path(__file__).parent / 'stock_codes_result.csv'
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['종목명', 'CSV종목코드', '추출된종목코드', '정식회사명', '일치여부']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n결과 저장: {output_path}")


if __name__ == '__main__':
    main()
