package com.example.stockkkkk.global.exception.custom;

/**
 * 서비스 이용 불가 상황에서 발생하는 예외
 * - 서버 점검 중
 * - 서비스 과부하
 * - 외부 서비스 장애
 */
public class ServiceUnavailableException extends RuntimeException {
    public ServiceUnavailableException(String message) {
        super(message);
    }

    public ServiceUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
