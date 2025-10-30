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
class ReturnServiceTest {

    @Autowired
    private ReturnService returnService;

    @Test
    void 서비스_주입_확인() {
        assertThat(returnService).isNotNull();
        System.out.println("ReturnService 정상 주입됨");
    }
}
