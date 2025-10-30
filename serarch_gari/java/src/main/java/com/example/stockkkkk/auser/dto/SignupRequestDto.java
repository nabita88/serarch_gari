package com.example.stockkkkk.auser.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@Schema(description = "회원가입 요청 데이터")
public class SignupRequestDto {

    @Schema(description = "사용자 이름", example = "홍길동", required = true)
    @NotBlank(message = "이름은 필수 입력 항목입니다.")
    @Pattern(regexp = "^[가-힣a-zA-Z\\s]+$", message = "이름은 한글 또는 영문만 입력 가능합니다.")
    @Size(min = 2, max = 50, message = "이름은 2자 이상 50자 이하로 입력해주세요.")
    private String name;

    @Schema(description = "사용자 이메일 주소", example = "user@example.com", required = true)
    @NotBlank(message = "이메일은 필수 입력 항목입니다.")
    @Email(message = "올바른 이메일 형식이 아닙니다.")
    private String email;

    @Schema(description = "사용자 비밀번호", example = "password123!", required = true, minLength = 8)
    @NotBlank(message = "비밀번호는 필수 입력 항목입니다.")
    @Size(min = 8, message = "비밀번호는 최소 8자 이상이어야 합니다.")
    private String password;

    @Schema(description = "비밀번호 확인", example = "password123!", required = true)
    @NotBlank(message = "비밀번호 확인은 필수 입력 항목입니다.")
    private String passwordConfirm;

    // 비밀번호 일치 검증 메서드
    public boolean isPasswordMatch() {
        return password != null && password.equals(passwordConfirm);
    }
}
