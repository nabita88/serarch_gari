package com.example.stockkkkk.news.service;

import com.example.stockkkkk.news.domain.StockDailyPrice;
import com.example.stockkkkk.news.repository.StockDailyPriceRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PriceServiceTest {

    @Mock
    private StockDailyPriceRepository priceRepository;

    @InjectMocks
    private PriceService priceService;

    private StockDailyPrice testPrice;

    @BeforeEach
    void setUp() {
        testPrice = createTestPrice("005930", LocalDate.now(), BigDecimal.valueOf(70000));
    }

    @Test
    @DisplayName("날짜 범위로 가격 조회")
    void findByDateRange() {
        when(priceRepository.findByStockCodeAndDateBetween(anyString(), any(LocalDate.class), any(LocalDate.class)))
                .thenReturn(List.of(testPrice));

        List<StockDailyPrice> result = priceService.findByDateRange("005930", "20240101", "20240131");

        assertThat(result).isNotEmpty();
        assertThat(result.get(0).getStockCode()).isEqualTo("005930");
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
