package com.example.stockkkkk.global.exception.novel;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;

/**
 * 공통 에러 응답 DTO
 * 모든 예외 상황에서 일관된 형태로 에러 정보를 반환
 */
@Getter
@Schema(description = "에러 응답")
public class ErrorResponse {

    @Schema(description = "에러 코드", example = "USER_NOT_FOUND")
    private final String code;

    @Schema(description = "에러 메시지", example = "존재하지 않는 사용자입니다.")
    private final String message;

    @Schema(description = "에러 발생 시간 (Unix timestamp)", example = "1640995200000")
    private final long timestamp;

    public ErrorResponse(String code, String message) {
        this.code = code;
        this.message = message;
        this.timestamp = System.currentTimeMillis();
    }

    public ErrorResponse(String code, String message, long timestamp) {
        this.code = code;
        this.message = message;
        this.timestamp = timestamp;
    }
}
