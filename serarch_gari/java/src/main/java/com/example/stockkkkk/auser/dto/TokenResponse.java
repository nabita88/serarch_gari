package com.example.stockkkkk.auser.dto;
import lombok.Getter;

@Getter
public class TokenResponse {

    private final String accessToken;
    private final String tokenType = "Bearer";

    public TokenResponse(String accessToken) {
        this.accessToken = accessToken;
    }
}
