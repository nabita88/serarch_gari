package com.example.stockkkkk.news.service;

import com.example.stockkkkk.news.domain.StockList;
import com.example.stockkkkk.news.repository.StockListRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@Disabled("서비스가 주석처리되어 비활성화")
@ExtendWith(MockitoExtension.class)
class StockServiceTest {

    @Mock
    private StockListRepository stockListRepository;

    @InjectMocks
    private StockService stockService;

    private StockList testStock;

    @BeforeEach
    void setUp() {
        testStock = createTestStock("005930", "삼성전자", "KOSPI");
    }

    @Test
    @DisplayName("종목 코드로 주식 조회 성공")
    void findByCode_Success() {
        when(stockListRepository.findByStockCode(anyString()))
                .thenReturn(Optional.of(testStock));

        StockList result = stockService.findByCode("005930");

        assertThat(result).isNotNull();
        assertThat(result.getStockCode()).isEqualTo("005930");
        assertThat(result.getKrxName()).isEqualTo("삼성전자");
    }

    @Test
    @DisplayName("존재하지 않는 종목 코드 조회 시 예외 발생")
    void findByCode_NotFound() {
        when(stockListRepository.findByStockCode(anyString()))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> stockService.findByCode("999999"))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("Stock not found");
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
