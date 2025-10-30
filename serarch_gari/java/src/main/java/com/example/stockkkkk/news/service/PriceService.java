package com.example.stockkkkk.news.service;

import com.example.stockkkkk.news.domain.StockDailyPrice;
import com.example.stockkkkk.news.repository.StockDailyPriceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PriceService {

    private final StockDailyPriceRepository priceRepository;
    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd");

    public List<StockDailyPrice> findByDateRange(String stockCode, String startDate, String endDate) {
        LocalDate start = LocalDate.parse(startDate, FORMATTER);
        LocalDate end = LocalDate.parse(endDate, FORMATTER);
        return priceRepository.findByStockCodeAndDateBetween(stockCode, start, end);
    }
}
