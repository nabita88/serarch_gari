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
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@Disabled("서비스가 주석처리되어 비활성화")
@ExtendWith(MockitoExtension.class)
class StockListServiceTest {

    @Mock
    private StockListRepository stockListRepository;

    @InjectMocks
    private StockListService stockListService;

    private StockList testStock1;
    private StockList testStock2;

    @BeforeEach
    void setUp() {
        testStock1 = createTestStock("005930", "삼성전자", "KOSPI");
        testStock2 = createTestStock("035720", "카카오", "KOSDAQ");
    }

    @Test
    @DisplayName("페이지네이션으로 전체 주식 목록 조회")
    void findAll_WithoutMarket() {
        Page<StockList> page = new PageImpl<>(List.of(testStock1, testStock2));
        when(stockListRepository.findAll(any(PageRequest.class)))
                .thenReturn(page);

        Page<StockList> result = stockListService.findAll(0, 20, null);

        assertThat(result.getContent()).hasSize(2);
    }

    @Test
    @DisplayName("특정 시장의 주식 목록 조회")
    void findAll_WithMarket() {
        Page<StockList> page = new PageImpl<>(List.of(testStock1));
        when(stockListRepository.findByMarket(anyString(), any(PageRequest.class)))
                .thenReturn(page);

        Page<StockList> result = stockListService.findAll(0, 20, "KOSPI");

        assertThat(result.getContent()).hasSize(1);
        assertThat(result.getContent().get(0).getMarket()).isEqualTo("KOSPI");
    }

    @Test
    @DisplayName("키워드로 주식 검색")
    void searchByName() {
        when(stockListRepository.findByKrxNameContaining(anyString()))
                .thenReturn(List.of(testStock1));

        List<StockList> result = stockListService.searchByName("삼성");

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getKrxName()).contains("삼성");
    }

    @Test
    @DisplayName("시장별 주식 개수 집계")
    void countByMarket() {
        when(stockListRepository.findAll())
                .thenReturn(List.of(testStock1, testStock2));

        Map<String, Long> result = stockListService.countByMarket();

        assertThat(result).containsKeys("KOSPI", "KOSDAQ");
    }

    @Test
    @DisplayName("모든 시장 목록 조회")
    void findAllMarkets() {
        when(stockListRepository.findDistinctMarkets())
                .thenReturn(List.of("KOSPI", "KOSDAQ"));

        List<String> result = stockListService.findAllMarkets();

        assertThat(result).containsExactly("KOSPI", "KOSDAQ");
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
