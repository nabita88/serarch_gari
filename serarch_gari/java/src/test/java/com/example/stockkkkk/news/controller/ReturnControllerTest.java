package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.domain.NewsReturn;
import com.example.stockkkkk.news.dto.ReturnAnalysisDto;
import com.example.stockkkkk.news.dto.ReturnAvgDto;
import com.example.stockkkkk.news.service.ReturnService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Disabled("서비스가 주석처리되어 비활성화")
@WebMvcTest(ReturnController.class)
class ReturnControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ReturnService returnService;

    @Test
    @DisplayName("GET /api/returns/{newsId} - 뉴스 ID로 수익률 조회")
    void getReturnByNewsId() throws Exception {
        NewsReturn newsReturn = createTestReturn("news123");
        when(returnService.findByNewsId(anyString()))
                .thenReturn(newsReturn);

        mockMvc.perform(get("/api/returns/news123"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.newsId").value("news123"));
    }

    @Test
    @DisplayName("GET /api/returns/avg-by-event/{eventCode} - 이벤트별 평균 수익률")
    void getAvgReturnByEvent() throws Exception {
        ReturnAvgDto avgDto = new ReturnAvgDto("EVENT_001", 0.05, 0.08, 10);
        when(returnService.calculateAvgByEvent(anyString()))
                .thenReturn(avgDto);

        mockMvc.perform(get("/api/returns/avg-by-event/EVENT_001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.eventCode").value("EVENT_001"))
                .andExpect(jsonPath("$.avgReturn1d").value(0.05));
    }

    @Test
    @DisplayName("GET /api/returns/stock/{stockCode} - 종목별 수익률 목록")
    void getReturnsByStock() throws Exception {
        NewsReturn newsReturn = createTestReturn("news123");
        when(returnService.findByStockCode(anyString(), anyInt()))
                .thenReturn(List.of(newsReturn));

        mockMvc.perform(get("/api/returns/stock/005930")
                        .param("days", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test
    @DisplayName("GET /api/returns/analysis/{stockCode} - 수익률 분석")
    void analyzeReturns() throws Exception {
        ReturnAnalysisDto analysisDto = new ReturnAnalysisDto("005930", 0.05, 0.08, 65.5, 20);
        when(returnService.analyzeReturns(anyString(), anyInt()))
                .thenReturn(analysisDto);

        mockMvc.perform(get("/api/returns/analysis/005930")
                        .param("days", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.stockCode").value("005930"))
                .andExpect(jsonPath("$.winRate").value(65.5));
    }

    private NewsReturn createTestReturn(String newsId) {
        return new NewsReturn() {
            {
                try {
                    var field = NewsReturn.class.getDeclaredField("newsId");
                    field.setAccessible(true);
                    field.set(this, newsId);

                    field = NewsReturn.class.getDeclaredField("return1d");
                    field.setAccessible(true);
                    field.set(this, BigDecimal.valueOf(0.055));

                    field = NewsReturn.class.getDeclaredField("return3d");
                    field.setAccessible(true);
                    field.set(this, BigDecimal.valueOf(0.08));
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        };
    }
}
