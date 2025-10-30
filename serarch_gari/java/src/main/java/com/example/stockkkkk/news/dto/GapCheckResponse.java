package com.example.stockkkkk.news.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

@Getter
@AllArgsConstructor
public class GapCheckResponse {
    @JsonProperty("stock_code")
    private String stockCode;
    
    @JsonProperty("stock_name")
    private String stockName;
    
    private Integer days;
    
    @JsonProperty("has_gap")
    private Boolean hasGap;
    
    @JsonProperty("gap_count")
    private Integer gapCount;
    
    @JsonProperty("gap_signals")
    private List<GapSignalDto> gapSignals;
    
    @JsonProperty("price_change")
    private Double priceChange;
}
