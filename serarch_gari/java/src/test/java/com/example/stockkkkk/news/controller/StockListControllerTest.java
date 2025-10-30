package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.domain.StockList;
import com.example.stockkkkk.news.service.StockListService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Disabled("서비스가 주석처리되어 비활성화")
@WebMvcTest(StockListController.class)
class StockListControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private StockListService stockListService;

    @Test
    @DisplayName("GET /api/stock-list - 전체 주식 목록 조회")
    void getAllStocks() throws Exception {
        StockList stock = createTestStock("005930", "삼성전자", "KOSPI");
        Page<StockList> page = new PageImpl<>(List.of(stock));
        when(stockListService.findAll(anyInt(), anyInt(), isNull()))
                .thenReturn(page);

        mockMvc.perform(get("/api/stock-list")
                        .param("page", "0")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content[0].stockCode").value("005930"));
    }

    @Test
    @DisplayName("GET /api/stock-list - 특정 시장 필터링")
    void getAllStocks_WithMarket() throws Exception {
        StockList stock = createTestStock("005930", "삼성전자", "KOSPI");
        Page<StockList> page = new PageImpl<>(List.of(stock));
        when(stockListService.findAll(anyInt(), anyInt(), anyString()))
                .thenReturn(page);

        mockMvc.perform(get("/api/stock-list")
                        .param("page", "0")
                        .param("size", "20")
                        .param("market", "KOSPI"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].market").value("KOSPI"));
    }

    @Test
    @DisplayName("GET /api/stock-list/search - 키워드 검색")
    void searchStocks() throws Exception {
        StockList stock = createTestStock("005930", "삼성전자", "KOSPI");
        when(stockListService.searchByName(anyString()))
                .thenReturn(List.of(stock));

        mockMvc.perform(get("/api/stock-list/search")
                        .param("keyword", "삼성"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$[0].krxName").value("삼성전자"));
    }

    @Test
    @DisplayName("GET /api/stock-list/count-by-market - 시장별 개수")
    void countByMarket() throws Exception {
        when(stockListService.countByMarket())
                .thenReturn(Map.of("KOSPI", 100L, "KOSDAQ", 200L));

        mockMvc.perform(get("/api/stock-list/count-by-market"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.KOSPI").value(100))
                .andExpect(jsonPath("$.KOSDAQ").value(200));
    }

    @Test
    @DisplayName("GET /api/stock-list/markets - 시장 목록")
    void getMarkets() throws Exception {
        when(stockListService.findAllMarkets())
                .thenReturn(List.of("KOSPI", "KOSDAQ"));

        mockMvc.perform(get("/api/stock-list/markets"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$[0]").value("KOSPI"))
                .andExpect(jsonPath("$[1]").value("KOSDAQ"));
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
