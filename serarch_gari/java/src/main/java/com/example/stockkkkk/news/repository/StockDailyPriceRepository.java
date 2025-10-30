package com.example.stockkkkk.news.repository;

import com.example.stockkkkk.news.domain.StockDailyPrice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
@Repository
public interface StockDailyPriceRepository extends JpaRepository<StockDailyPrice, Long> {
    
    List<StockDailyPrice> findByStockCodeAndDateBetween(String stockCode, LocalDate startDate, LocalDate endDate);
    
    @Query("SELECT p FROM StockDailyPrice p WHERE p.stockCode = :stockCode AND p.date = :date")
    Optional<StockDailyPrice> findByStockCodeAndDate(
        @Param("stockCode") String stockCode, 
        @Param("date") LocalDate date
    );
}
