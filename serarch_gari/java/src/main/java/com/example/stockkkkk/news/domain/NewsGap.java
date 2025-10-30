package com.example.stockkkkk.news.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "news_gaps")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
public class NewsGap {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "news_id", length = 500, nullable = false)
    private String newsId;

    @Column(name = "news_title", columnDefinition = "TEXT")
    private String newsTitle;

    @Column(name = "stock_code", length = 10, nullable = false)
    private String stockCode;

    @Column(name = "stock_name", length = 100)
    private String stockName;

    @Column(name = "event_code", length = 50, nullable = false)
    private String eventCode;

    @Column(name = "news_date")
    private LocalDate newsDate;

    @Column(name = "horizon", nullable = false)
    private Integer horizon;

    @Column(name = "actual_return", precision = 10, scale = 6, nullable = false)
    private BigDecimal actualReturn;

    @Column(name = "expected_return", precision = 10, scale = 6, nullable = false)
    private BigDecimal expectedReturn;

    @Column(name = "expected_std", precision = 10, scale = 6, nullable = false)
    private BigDecimal expectedStd;

    @Column(name = "z_score", precision = 10, scale = 4, nullable = false)
    private BigDecimal zScore;

    @Column(name = "direction", length = 10, nullable = false)
    private String direction;

    @Column(name = "magnitude", length = 20, nullable = false)
    private String magnitude;

    @Column(name = "sample_count")
    private Integer sampleCount;

    @CreationTimestamp
    @Column(name = "detected_at")
    private LocalDateTime detectedAt;
}
