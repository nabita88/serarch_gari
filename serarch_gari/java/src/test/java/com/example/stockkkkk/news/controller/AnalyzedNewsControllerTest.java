package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.service.AnalyzedNewsService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Disabled("서비스가 주석처리되어 비활성화")
@WebMvcTest(AnalyzedNewsController.class)
class AnalyzedNewsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AnalyzedNewsService analyzedNewsService;

    @Test
    void getAnalyzedNews() throws Exception {
        when(analyzedNewsService.findWithFilters(null, null, null))
            .thenReturn(List.of());

        mockMvc.perform(get("/api/analyzed-news"))
            .andExpect(status().isOk());
    }

    @Test
    void getNewsByTruth() throws Exception {
        when(analyzedNewsService.findByTruthValue("TRUE"))
            .thenReturn(List.of());

        mockMvc.perform(get("/api/analyzed-news/truth/TRUE"))
            .andExpect(status().isOk());
    }

    @Test
    void getEventStats() throws Exception {
        when(analyzedNewsService.countByEvents())
            .thenReturn(Map.of());

        mockMvc.perform(get("/api/analyzed-news/stats/events"))
            .andExpect(status().isOk());
    }

    @Test
    void getSentimentStats() throws Exception {
        when(analyzedNewsService.countBySentiment())
            .thenReturn(Map.of());

        mockMvc.perform(get("/api/analyzed-news/stats/sentiment"))
            .andExpect(status().isOk());
    }
}
