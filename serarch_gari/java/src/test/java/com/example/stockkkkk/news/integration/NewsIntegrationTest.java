package com.example.stockkkkk.news.integration;

import com.example.stockkkkk.news.domain.NewsGap;
import com.example.stockkkkk.news.domain.StockList;
import com.example.stockkkkk.news.repository.NewsGapRepository;
import com.example.stockkkkk.news.repository.StockListRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class NewsIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private StockListRepository stockListRepository;

    @Autowired
    private NewsGapRepository newsGapRepository;

    @Test
    @DisplayName("통합 테스트: 주식 목록 API 조회")
    void integrationTest_StockList() throws Exception {
        mockMvc.perform(get("/api/stock-list")
                        .param("page", "0")
                        .param("size", "20"))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("통합 테스트: 갭 통계 API 조회")
    void integrationTest_GapStats() throws Exception {
        mockMvc.perform(get("/api/gaps/stats")
                        .param("days", "7"))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("통합 테스트: 시장 목록 조회")
    void integrationTest_Markets() throws Exception {
        mockMvc.perform(get("/api/stock-list/markets"))
                .andExpect(status().isOk());
    }
}
