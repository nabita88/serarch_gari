package com.example.stockkkkk.news.service;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Transactional
@Disabled
class GapServiceTest {

    @Autowired
    private GapService gapService;

    @Test
    void 서비스_주입_확인() {
        assertThat(gapService).isNotNull();
        System.out.println("GapService 정상 주입됨");
    }
}
