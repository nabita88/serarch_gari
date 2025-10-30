package com.example.stockkkkk.news.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

@Entity
@Table(name = "rumors_opendart")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
public class RumorsOpendart {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "market", columnDefinition = "TEXT")
    private String market;

    @Column(name = "stock_code", columnDefinition = "TEXT")
    private String stockCode;

    @Column(name = "krx_name", columnDefinition = "TEXT")
    private String krxName;

    @Column(name = "corp_code")
    private Long corpCode;
}
