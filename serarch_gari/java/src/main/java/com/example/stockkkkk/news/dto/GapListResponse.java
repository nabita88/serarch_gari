package com.example.stockkkkk.news.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

@Getter
@AllArgsConstructor
public class GapListResponse {
    private List<GapHistoryDto> gaps;
}
