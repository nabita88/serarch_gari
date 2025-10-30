package com.example.stockkkkk.global.auth.jwt;

import com.example.stockkkkk.global.auth.jwt.JwtTokenProvider;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider jwtTokenProvider;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        try {
            authenticateUser(request);
        } catch (Exception e) {
            log.error("JWT authentication failed: {}", e.getMessage());
            // 인증 실패 시에도 필터 체인 계속 진행 (Spring Security가 처리)
        }

        filterChain.doFilter(request, response);
    }

    /**
     * 사용자 인증 처리
     * JWT 토큰을 검증하고 SecurityContext에 인증 정보 설정
     */
    private void authenticateUser(HttpServletRequest request) {
        String token = resolveToken(request);

        if (isValidToken(token)) {
            Authentication authentication = createAuthentication(token);
            setSecurityContext(authentication);
            log.debug("JWT authentication successful for user: {}", authentication.getName());
        }
    }

    /**
     * 토큰 유효성 검사
     */
    private boolean isValidToken(String token) {
        return StringUtils.hasText(token) && jwtTokenProvider.validateToken(token);
    }

    /**
     * JWT 토큰으로부터 Authentication 객체 생성
     */
    private Authentication createAuthentication(String token) {
        String username = jwtTokenProvider.getUsername(token);
        String role = jwtTokenProvider.getRole(token);

        return new UsernamePasswordAuthenticationToken(
                username,
                null,
                List.of(new SimpleGrantedAuthority("ROLE_" + role))
        );
    }

    /**
     * SecurityContext에 인증 정보 설정
     */
    private void setSecurityContext(Authentication authentication) {
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    /**
     * HTTP 요청 헤더에서 JWT 토큰 추출
     * Authorization: Bearer {token} 형태에서 토큰 부분만 반환
     */
    private String resolveToken(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }
}
