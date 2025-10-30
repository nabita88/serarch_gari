package com.example.stockkkkk.news.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@AllArgsConstructor
public class GapHistoryDto {
    @JsonProperty("stock_name")
    private String stockName;
    
    @JsonProperty("stock_code")
    private String stockCode;
    
    @JsonProperty("event_code")
    private String eventCode;
    
    private LocalDate date;
    
    private String direction;
    
    private String magnitude;
    
    @JsonProperty("z_score")
    private Double zScore;
}
