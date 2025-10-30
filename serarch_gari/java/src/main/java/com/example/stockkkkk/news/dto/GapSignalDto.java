package com.example.stockkkkk.news.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@AllArgsConstructor
public class GapSignalDto {
    @JsonProperty("news_id")
    private String newsId;
    
    @JsonProperty("news_title")
    private String newsTitle;
    
    @JsonProperty("event_code")
    private String eventCode;
    
    @JsonProperty("news_date")
    private LocalDate newsDate;
    
    private Integer horizon;
    
    @JsonProperty("z_score")
    private Double zScore;
    
    private String direction;
    
    private String magnitude;
    
    @JsonProperty("actual_return")
    private Double actualReturn;
    
    @JsonProperty("expected_return")
    private Double expectedReturn;
    
    @JsonProperty("sample_count")
    private Integer sampleCount;
}
