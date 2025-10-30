package com.example.stockkkkk.auser.controller;

import com.example.stockkkkk.auser.dto.LoginRequestDto;
import com.example.stockkkkk.auser.dto.SignupRequestDto;
import com.example.stockkkkk.auser.dto.TokenResponse;
import com.example.stockkkkk.auser.dto.UserResponse;
import com.example.stockkkkk.auser.service.UserService;
import com.example.stockkkkk.global.exception.custom.PasswordMismatchException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api/ausers")
@RequiredArgsConstructor
@Tag(name = "User API", description = "사용자 관련 API")
public class UserController {

    private final UserService userService;

    @Operation(summary = "회원가입", description = "새로운 사용자 계정을 생성합니다.")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "201", description = "회원가입 성공"),
            @ApiResponse(responseCode = "400", description = "잘못된 요청 데이터 (비밀번호 불일치, 유효성 검증 실패)"),
            @ApiResponse(responseCode = "409", description = "이미 존재하는 이메일"),
            @ApiResponse(responseCode = "500", description = "서버 내부 오류 (데이터베이스 연결 실패, 토큰 생성 실패 등)"),
            @ApiResponse(responseCode = "503", description = "서비스 이용 불가 (서버 점검, 과부하 등)")
    })
    @PostMapping("/regCreate")
    public ResponseEntity<TokenResponse> regCreate(@Valid @RequestBody SignupRequestDto request) {
        // 비밀번호 일치 검증
        if (!request.isPasswordMatch()) {
            throw new PasswordMismatchException("비밀번호가 일치하지 않습니다.");
        }

        TokenResponse response = userService.regCreate(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @Operation(summary = "로그인", description = "사용자 인증 후 JWT 토큰을 발급합니다.")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "로그인 성공"),
            @ApiResponse(responseCode = "400", description = "잘못된 요청 데이터 (유효성 검증 실패)"),
            @ApiResponse(responseCode = "401", description = "인증 실패 (이메일 또는 비밀번호 불일치)"),
            @ApiResponse(responseCode = "404", description = "존재하지 않는 사용자"),
            @ApiResponse(responseCode = "500", description = "서버 내부 오류 (데이터베이스 연결 실패, 토큰 생성 실패 등)"),
            @ApiResponse(responseCode = "503", description = "서비스 이용 불가 (서버 점검, 인증 서비스 장애 등)")
    })
    @PostMapping("/openSession")
    public ResponseEntity<TokenResponse> openSession(@Valid @RequestBody LoginRequestDto request) {
        TokenResponse response = userService.openSession(request);
        return ResponseEntity.ok(response);
    }

    @Operation(summary = "내 정보 조회", description = "현재 로그인한 사용자의 정보를 조회합니다.")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "사용자 정보 조회 성공"),
            @ApiResponse(responseCode = "401", description = "인증되지 않은 사용자 (토큰 만료, 유효하지 않은 토큰)"),
            @ApiResponse(responseCode = "403", description = "접근 권한 없음"),
            @ApiResponse(responseCode = "404", description = "사용자를 찾을 수 없음"),
            @ApiResponse(responseCode = "500", description = "서버 내부 오류 (데이터베이스 연결 실패 등)"),
            @ApiResponse(responseCode = "503", description = "서비스 이용 불가 (서버 점검, 데이터베이스 서비스 장애 등)")
    })
    @GetMapping("/me")
    public ResponseEntity<UserResponse> getCurrentUser(
            @Parameter(hidden = true) Authentication authentication) {
        String email = authentication.getName();
        UserResponse response = userService.findByEmail(email);
        return ResponseEntity.ok(response);
    }
}
