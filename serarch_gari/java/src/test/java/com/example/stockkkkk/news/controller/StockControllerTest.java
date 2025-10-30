package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.domain.StockList;
import com.example.stockkkkk.news.service.StockService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Disabled("서비스가 주석처리되어 비활성화")
@WebMvcTest(StockController.class)
class StockControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private StockService stockService;

    @Test
    @DisplayName("GET /api/stocks/{stockCode} - 종목 정보 조회")
    void getStockInfo() throws Exception {
        StockList stock = createTestStock("005930", "삼성전자", "KOSPI");
        when(stockService.findByCode(anyString()))
                .thenReturn(stock);

        mockMvc.perform(get("/api/stocks/005930"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.stockCode").value("005930"))
                .andExpect(jsonPath("$.krxName").value("삼성전자"))
                .andExpect(jsonPath("$.market").value("KOSPI"));
    }

    @Test
    @DisplayName("GET /api/stocks/{stockCode} - 존재하지 않는 종목")
    void getStockInfo_NotFound() throws Exception {
        when(stockService.findByCode(anyString()))
                .thenThrow(new RuntimeException("Stock not found: 999999"));

        mockMvc.perform(get("/api/stocks/999999"))
                .andExpect(status().is5xxServerError());
    }

    private StockList createTestStock(String stockCode, String krxName, String market) {
        return new StockList() {
            {
                try {
                    var field = StockList.class.getDeclaredField("stockCode");
                    field.setAccessible(true);
                    field.set(this, stockCode);

                    field = StockList.class.getDeclaredField("krxName");
                    field.setAccessible(true);
                    field.set(this, krxName);

                    field = StockList.class.getDeclaredField("market");
                    field.setAccessible(true);
                    field.set(this, market);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        };
    }
}
