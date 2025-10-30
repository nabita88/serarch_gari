package com.example.stockkkkk.news.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class GapStats {
    private long totalCount;
    private long overCount;
    private long underCount;
    private Double avgZScore;
}
