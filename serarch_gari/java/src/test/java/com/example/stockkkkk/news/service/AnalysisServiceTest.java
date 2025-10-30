package com.example.stockkkkk.news.service;

import com.example.stockkkkk.news.domain.NewsGap;
import com.example.stockkkkk.news.domain.NewsReturn;
import com.example.stockkkkk.news.domain.StockDailyPrice;
import com.example.stockkkkk.news.dto.CorrelationDto;
import com.example.stockkkkk.news.dto.EventPerformanceDto;
import com.example.stockkkkk.news.dto.GapReturnComparisonDto;
import com.example.stockkkkk.news.repository.NewsGapRepository;
import com.example.stockkkkk.news.repository.NewsReturnRepository;
import com.example.stockkkkk.news.repository.StockDailyPriceRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@Disabled("서비스가 주석처리되어 비활성화")
@ExtendWith(MockitoExtension.class)
class AnalysisServiceTest {

    @Mock
    private NewsGapRepository gapRepository;

    @Mock
    private NewsReturnRepository returnRepository;

    @Mock
    private StockDailyPriceRepository priceRepository;

    @InjectMocks
    private AnalysisService analysisService;

    private NewsGap testGap;
    private NewsReturn testReturn;
    private StockDailyPrice testPrice1;
    private StockDailyPrice testPrice2;

    @BeforeEach
    void setUp() {
        testGap = createTestGap();
        testReturn = createTestReturn();
        testPrice1 = createTestPrice("005930", LocalDate.now().minusDays(5), BigDecimal.valueOf(70000));
        testPrice2 = createTestPrice("005930", LocalDate.now().minusDays(4), BigDecimal.valueOf(71000));
    }

    @Test
    @DisplayName("갭과 수익률 비교 분석")
    void compareGapAndReturn() {
        when(gapRepository.findByStockCodeAndNewsDateAfter(anyString(), any(LocalDate.class)))
                .thenReturn(List.of(testGap));
        when(returnRepository.findByNewsId(anyString()))
                .thenReturn(Optional.of(testReturn));

        List<GapReturnComparisonDto> result = analysisService.compareGapAndReturn("005930", 7);

        assertThat(result).isNotEmpty();
        assertThat(result.get(0).getNewsId()).isEqualTo("news123");
    }

    @Test
    @DisplayName("두 주식 간 상관관계 계산")
    void calculateCorrelation() {
        when(priceRepository.findByStockCodeAndDateBetween(anyString(), any(LocalDate.class), any(LocalDate.class)))
                .thenReturn(List.of(testPrice1, testPrice2));

        CorrelationDto result = analysisService.calculateCorrelation("005930", "000660", 30);

        assertThat(result).isNotNull();
        assertThat(result.getStock1()).isEqualTo("005930");
        assertThat(result.getStock2()).isEqualTo("000660");
    }

    @Test
    @DisplayName("이벤트 성과 분석")
    void analyzeEventPerformance() {
        when(gapRepository.findAll()).thenReturn(List.of(testGap));

        EventPerformanceDto result = analysisService.analyzeEventPerformance("EVENT_001", 30);

        assertThat(result).isNotNull();
        assertThat(result.getEventCode()).isEqualTo("EVENT_001");
    }

    private NewsGap createTestGap() {
        return new NewsGap() {
            {
                try {
                    var field = NewsGap.class.getDeclaredField("newsId");
                    field.setAccessible(true);
                    field.set(this, "news123");
                    
                    field = NewsGap.class.getDeclaredField("stockCode");
                    field.setAccessible(true);
                    field.set(this, "005930");
                    
                    field = NewsGap.class.getDeclaredField("eventCode");
                    field.setAccessible(true);
                    field.set(this, "EVENT_001");
                    
                    field = NewsGap.class.getDeclaredField("newsDate");
                    field.setAccessible(true);
                    field.set(this, LocalDate.now());
                    
                    field = NewsGap.class.getDeclaredField("expectedReturn");
                    field.setAccessible(true);
                    field.set(this, BigDecimal.valueOf(0.05));
                    
                    field = NewsGap.class.getDeclaredField("actualReturn");
                    field.setAccessible(true);
                    field.set(this, BigDecimal.valueOf(0.06));
                    
                    field = NewsGap.class.getDeclaredField("zScore");
                    field.setAccessible(true);
                    field.set(this, BigDecimal.valueOf(2.5));
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        };
    }

    private NewsReturn createTestReturn() {
        return new NewsReturn() {
            {
                try {
                    var field = NewsReturn.class.getDeclaredField("newsId");
                    field.setAccessible(true);
                    field.set(this, "news123");
                    
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
