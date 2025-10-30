package com.example.stockkkkk.news.controller;

import com.example.stockkkkk.news.domain.StockDailyPrice;
import com.example.stockkkkk.news.service.PriceService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PriceController.class)
class PriceControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private PriceService priceService;

    @Test
    @DisplayName("GET /api/prices/{stockCode} - 가격 조회")
    void getPrices() throws Exception {
        StockDailyPrice price = createTestPrice("005930", LocalDate.now(), BigDecimal.valueOf(70000));
        when(priceService.findByDateRange(anyString(), anyString(), anyString()))
                .thenReturn(List.of(price));

        mockMvc.perform(get("/api/prices/005930")
                        .param("startDate", "20240101")
                        .param("endDate", "20240131"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$[0].stockCode").value("005930"));
    }

    private StockDailyPrice createTestPrice(String stockCode, LocalDate date, BigDecimal price) {
        return new StockDailyPrice() {
            {
                try {
                    var field = StockDailyPrice.class.getDeclaredField("stockCode");
                    field.setAccessible(true);
                    field.set(this, stockCode);

                    field = StockDailyPrice.class.getDeclaredField("date");
                    field.setAccessible(true);
                    field.set(this, date);

                    field = StockDailyPrice.class.getDeclaredField("closingPrice");
                    field.setAccessible(true);
                    field.set(this, price);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        };
    }
}
