
package com.example.stockkkkk.auser.service;
import com.example.stockkkkk.auser.domain.Ausers;
import com.example.stockkkkk.auser.domain.UserRole;
import com.example.stockkkkk.auser.dto.LoginRequestDto;
import com.example.stockkkkk.auser.dto.SignupRequestDto;
import com.example.stockkkkk.auser.dto.TokenResponse;
import com.example.stockkkkk.auser.dto.UserResponse;
import com.example.stockkkkk.auser.repository.UserRepository;

import com.example.stockkkkk.global.auth.jwt.JwtTokenProvider;
import com.example.stockkkkk.global.exception.custom.DuplicateEmailException;
import com.example.stockkkkk.global.exception.custom.PasswordMismatchException;
import com.example.stockkkkk.global.exception.custom.UserNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    @Transactional
    public TokenResponse regCreate(SignupRequestDto request) {
        // 이메일 중복 검증
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new DuplicateEmailException("이미 등록된 이메일입니다: " + request.getEmail());
        }

        // 비밀번호 일치 검증 (컨트롤러에서 체크하지만 서비스에서도 이중 검증)
        if (!request.isPasswordMatch()) {
            throw new PasswordMismatchException("비밀번호가 일치하지 않습니다.");
        }

        Ausers user = Ausers.builder()
                .name(request.getName())
                .email(request.getEmail())
                .password(passwordEncoder.encode(request.getPassword()))
                .role(UserRole.USER)
                .build();

        Ausers savedUser = userRepository.save(user);
        log.info("새 사용자 회원가입: {} ({})", savedUser.getName(), savedUser.getEmail());

        // 회원가입 완료 후 자동 로그인을 위한 토큰 생성
        String token = jwtTokenProvider.createToken(savedUser.getEmail(), savedUser.getRole().name());
        return new TokenResponse(token);
    }

    public TokenResponse openSession(LoginRequestDto request) {
        Ausers user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new UserNotFoundException("존재하지 않는 이메일입니다: " + request.getEmail()));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new PasswordMismatchException("비밀번호가 일치하지 않습니다.");
        }

        String token = jwtTokenProvider.createToken(user.getEmail(), user.getRole().name());
        log.info("사용자 로그인: {} ({})", user.getName(), user.getEmail());

        return new TokenResponse(token);
    }

    public UserResponse findByUsername(String email) {
        Ausers user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UserNotFoundException("존재하지 않는 사용자입니다: " + email));

        return new UserResponse(user);
    }

    public UserResponse findByEmail(String email) {
        Ausers user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UserNotFoundException("존재하지 않는 사용자입니다: " + email));

        return new UserResponse(user);
    }

    private void validateDuplicateUser(String email) {
        if (userRepository.existsByEmail(email)) {
            throw new DuplicateEmailException("이미 등록된 이메일입니다: " + email);
        }
    }
}
