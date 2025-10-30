package com.example.stockkkkk.news.service;

import com.example.stockkkkk.news.domain.NewsGap;
import com.example.stockkkkk.news.domain.StockDailyPrice;
import com.example.stockkkkk.news.dto.*;
import com.example.stockkkkk.news.repository.NewsGapRepository;
import com.example.stockkkkk.news.repository.StockDailyPriceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class GapService {

    private final NewsGapRepository gapRepository;
    private final StockDailyPriceRepository priceRepository;

    public GapCheckResponse checkGaps(String stockCode, int days) {
        LocalDate startDate = LocalDate.now().minusDays(days);
        List<NewsGap> gaps = gapRepository.findByStockCodeAndNewsDateAfter(stockCode, startDate);
        
        String stockName = gaps.isEmpty() ? null : gaps.get(0).getStockName();
        boolean hasGap = !gaps.isEmpty();
        int gapCount = gaps.size();
        
        List<GapSignalDto> signals = gaps.stream()
            .map(gap -> new GapSignalDto(
                gap.getNewsId(),
                gap.getNewsTitle(),
                gap.getEventCode(),
                gap.getNewsDate(),
                gap.getHorizon(),
                gap.getZScore() != null ? gap.getZScore().doubleValue() : null,
                gap.getDirection(),
                gap.getMagnitude(),
                gap.getActualReturn() != null ? gap.getActualReturn().doubleValue() : null,
                gap.getExpectedReturn() != null ? gap.getExpectedReturn().doubleValue() : null,
                gap.getSampleCount()
            ))
            .toList();
        
        Double priceChange = calculatePriceChange(stockCode, days);
        
        return new GapCheckResponse(stockCode, stockName, days, hasGap, gapCount, signals, priceChange);
    }

    public Double calculatePriceChange(String stockCode, int days) {
        LocalDate endDate = LocalDate.now();
        LocalDate startDate = endDate.minusDays(days);
        
        Optional<StockDailyPrice> startPrice = priceRepository.findByStockCodeAndDate(stockCode, startDate);
        Optional<StockDailyPrice> endPrice = priceRepository.findByStockCodeAndDate(stockCode, endDate);
        
        if (startPrice.isEmpty() || endPrice.isEmpty()) {
            List<StockDailyPrice> prices = priceRepository.findByStockCodeAndDateBetween(
                stockCode, startDate, endDate
            );
            
            if (prices.size() < 2) {
                return null;
            }
            
            prices.sort(Comparator.comparing(StockDailyPrice::getDate));
            BigDecimal firstPrice = prices.get(0).getClosingPrice();
            BigDecimal lastPrice = prices.get(prices.size() - 1).getClosingPrice();
            
            if (firstPrice == null || lastPrice == null || firstPrice.doubleValue() == 0) {
                return null;
            }
            
            return (lastPrice.doubleValue() - firstPrice.doubleValue()) 
                   / firstPrice.doubleValue() * 100.0;
        }
        
        BigDecimal start = startPrice.get().getClosingPrice();
        BigDecimal end = endPrice.get().getClosingPrice();
        
        if (start == null || end == null || start.doubleValue() == 0) {
            return null;
        }
        
        return (end.doubleValue() - start.doubleValue()) / start.doubleValue() * 100.0;
    }

    public List<GapHistoryDto> findGapsWithFilters(int days, String direction, String magnitude, double minZ, int limit) {
        LocalDate afterDate = LocalDate.now().minusDays(days);
        List<NewsGap> gaps = gapRepository.findGapsWithFilters(afterDate, direction, magnitude, minZ);
        return gaps.stream()
            .limit(limit)
            .map(gap -> new GapHistoryDto(
                gap.getStockName(),
                gap.getStockCode(),
                gap.getEventCode(),
                gap.getNewsDate(),
                gap.getDirection(),
                gap.getMagnitude(),
                gap.getZScore() != null ? gap.getZScore().doubleValue() : null
            ))
            .toList();
    }

    public GapStats calculateStats(int days) {
        LocalDate afterDate = LocalDate.now().minusDays(days);
        long totalCount = gapRepository.countByNewsDateAfter(afterDate);
        long overCount = gapRepository.countOverByNewsDateAfter(afterDate);
        long underCount = gapRepository.countUnderByNewsDateAfter(afterDate);
        Double avgZScore = gapRepository.avgZScoreByNewsDateAfter(afterDate);
        
        return new GapStats(totalCount, overCount, underCount, avgZScore);
    }

    public GapStatisticsDto calculateDetailedStats(int days) {
        LocalDate afterDate = LocalDate.now().minusDays(days);
        List<NewsGap> gaps = gapRepository.findAll().stream()
            .filter(gap -> gap.getNewsDate() != null && !gap.getNewsDate().isBefore(afterDate))
            .toList();

        log.info("Total gaps found: {}", gaps.size());
        log.info("UNDER gaps: {}", gaps.stream().filter(g -> "UNDER".equals(g.getDirection())).count());
        log.info("OVER gaps: {}", gaps.stream().filter(g -> "OVER".equals(g.getDirection())).count());

        GapStatisticsDto stats = new GapStatisticsDto();
        stats.setPeriodDays(days);
        stats.setTotal(gaps.size());

        // Direction 집계
        Map<String, Long> byDirection = gaps.stream()
            .filter(gap -> gap.getDirection() != null)
            .collect(Collectors.groupingBy(NewsGap::getDirection, Collectors.counting()));
        log.info("byDirection map: {}", byDirection);
        stats.setByDirection(byDirection);

        // Magnitude 집계
        Map<String, Long> byMagnitude = gaps.stream()
            .filter(gap -> gap.getMagnitude() != null)
            .collect(Collectors.groupingBy(NewsGap::getMagnitude, Collectors.counting()));
        stats.setByMagnitude(byMagnitude);

        // Event Code 집계
        Map<String, Long> byEventCode = gaps.stream()
            .filter(gap -> gap.getEventCode() != null)
            .collect(Collectors.groupingBy(NewsGap::getEventCode, Collectors.counting()));
        stats.setByEventCode(byEventCode);

        return stats;
    }
}
