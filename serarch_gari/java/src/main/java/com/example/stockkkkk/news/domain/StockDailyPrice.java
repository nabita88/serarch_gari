package com.example.stockkkkk.news.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Objects;

@Entity
@Table(name = "stock_daily_prices")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
@IdClass(StockDailyPrice.StockDailyPriceId.class)
public class StockDailyPrice {

    @Id
    @Column(name = "stock_code", length = 10)
    private String stockCode;

    @Id
    @Column(name = "trade_date")
    private LocalDate date;

    @Column(name = "stock_name", length = 100)
    private String stockName;

    @Column(name = "close_price", precision = 15, scale = 2)
    private BigDecimal closingPrice;

    @Getter
    @NoArgsConstructor
    public static class StockDailyPriceId implements Serializable {
        private String stockCode;
        private LocalDate date;

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            StockDailyPriceId that = (StockDailyPriceId) o;
            return Objects.equals(stockCode, that.stockCode) && Objects.equals(date, that.date);
        }

        @Override
        public int hashCode() {
            return Objects.hash(stockCode, date);
        }
    }
}
