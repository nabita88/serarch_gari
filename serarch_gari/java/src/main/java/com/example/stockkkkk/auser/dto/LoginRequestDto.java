package com.example.stockkkkk.auser.dto;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@Schema(description = "로그인 요청 데이터")
public class LoginRequestDto {

    @Schema(description = "사용자 이메일 주소", example = "user@example.com", required = true)
    @NotBlank(message = "이메일은 필수 입력 항목입니다.")
    @Email(message = "올바른 이메일 형식이 아닙니다.")
    private String email;

    @Schema(description = "사용자 비밀번호", example = "password123!", required = true)
    @NotBlank(message = "비밀번호는 필수 입력 항목입니다.")
    private String password;
}
