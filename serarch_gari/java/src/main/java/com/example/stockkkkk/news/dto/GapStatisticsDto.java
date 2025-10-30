package com.example.stockkkkk.news.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

import java.util.HashMap;
import java.util.Map;

@Getter
@Setter
@AllArgsConstructor
public class GapStatisticsDto {
    @JsonProperty("period_days")
    private int periodDays;
    
    private long total;
    
    @JsonProperty("by_direction")
    private Map<String, Long> byDirection;
    
    @JsonProperty("by_magnitude")
    private Map<String, Long> byMagnitude;
    
    @JsonProperty("by_event_code")
    private Map<String, Long> byEventCode;

    public GapStatisticsDto() {
        this.byDirection = new HashMap<>();
        this.byMagnitude = new HashMap<>();
        this.byEventCode = new HashMap<>();
    }
}
